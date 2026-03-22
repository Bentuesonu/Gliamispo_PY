import re
import pickle
import threading

from gliamispo.models.scene_element import SceneElement


_NOUN_CHUNK_RE = re.compile(
    r'\b([A-ZÀÈÉÌÒÙ][a-zàèéìòùA-Z]{2,}(?:\s+[A-Za-zàèéìòù]{2,}){0,3})\b'
)


def _extract_candidates(text):
    candidates = []
    seen = set()

    for m in _NOUN_CHUNK_RE.finditer(text):
        candidate = m.group(1).strip()
        if candidate.lower() not in seen and len(candidate) > 2:
            seen.add(candidate.lower())
            candidates.append(candidate)

    if not candidates:
        words = [w for w in text.split() if len(w) > 3]
        candidates = [' '.join(words[:3])] if words else [text[:30]]

    return candidates[:5]


class SklearnInference:
    def __init__(self, model_path):
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)
        self._vectorizer = bundle["vectorizer"]
        self._clf = bundle["classifier"]
        self._lock = threading.Lock()

    def predict(self, text, max_results=5, min_confidence=0.30):
        candidates = _extract_candidates(text)
        results = []
        seen = set()

        with self._lock:
            for candidate in candidates:
                X = self._vectorizer.transform([candidate])
                if hasattr(self._clf, "predict_proba"):
                    probs = self._clf.predict_proba(X)[0]
                    classes = self._clf.classes_
                    label_id = int(probs.argmax())
                    category = classes[label_id]
                    confidence = float(probs[label_id])
                elif hasattr(self._clf, "decision_function"):
                    scores = self._clf.decision_function(X)[0]
                    exp_s = [max(0.0, s) for s in scores]
                    total = sum(exp_s) or 1.0
                    probs_norm = [e / total for e in exp_s]
                    label_id = int(max(range(len(probs_norm)),
                                       key=lambda i: probs_norm[i]))
                    category = self._clf.classes_[label_id]
                    confidence = probs_norm[label_id]
                else:
                    continue

                if confidence < min_confidence:
                    continue

                key = (category, candidate)
                if key in seen:
                    continue
                seen.add(key)

                results.append(SceneElement(
                    category=category,
                    element_name=candidate,
                    ai_suggested=1,
                    ai_confidence=round(confidence, 4),
                    detection_method="sklearn",
                ))

                if len(results) >= max_results:
                    break

        return results


class OnnxInference:
    def __init__(self, model_path):
        import onnxruntime as ort
        import json, os

        self._session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"]
        )
        self._lock = threading.Lock()

        meta_path = model_path.replace(".onnx", ".meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            self._vocab = meta.get("vocab", {})
            self._id2label = {
                int(k): v for k, v in meta.get("id2label", {}).items()
            }
        else:
            self._vocab = {}
            self._id2label = {}

    def _tokenize(self, text, max_len=128):
        tokens = text.lower().split()[:max_len - 2]

        cls_id = self._vocab.get("[CLS]", 101)
        sep_id = self._vocab.get("[SEP]", 102)
        unk_id = self._vocab.get("[UNK]", 100)
        pad_id = self._vocab.get("[PAD]", 0)

        ids = [cls_id] + [self._vocab.get(t, unk_id) for t in tokens] + [sep_id]
        mask = [1] * len(ids)

        pad_len = max_len - len(ids)
        ids  += [pad_id] * pad_len
        mask += [0] * pad_len

        return {
            "input_ids": [ids],
            "attention_mask": [mask],
        }

    def predict(self, text, max_results=5, min_confidence=0.30):
        if not self._vocab or not self._id2label:
            return []

        import numpy as np
        from scipy.special import softmax

        with self._lock:
            inputs = self._tokenize(text)
            valid_names = [inp.name for inp in self._session.get_inputs()]
            ort_inputs = {
                k: np.array(v, dtype=np.int64)
                for k, v in inputs.items()
                if k in valid_names
            }
            logits = self._session.run(None, ort_inputs)[0]

        probs = softmax(logits[0], axis=-1)
        tokens = text.lower().split()

        entities = []
        current_entity = []
        current_cat = None
        current_conf = []

        for i, token_probs in enumerate(probs[1:len(tokens) + 1]):
            label_id = int(np.argmax(token_probs))
            label = self._id2label.get(label_id, "O")
            confidence = float(token_probs[label_id])

            if label.startswith("B-"):
                if current_entity:
                    avg_conf = sum(current_conf) / len(current_conf)
                    if avg_conf >= min_confidence:
                        entities.append((' '.join(current_entity), current_cat, avg_conf))
                current_entity = [tokens[i] if i < len(tokens) else ""]
                current_cat = label[2:]
                current_conf = [confidence]
            elif label.startswith("I-") and current_cat:
                current_entity.append(tokens[i] if i < len(tokens) else "")
                current_conf.append(confidence)
            else:
                if current_entity:
                    avg_conf = sum(current_conf) / len(current_conf)
                    if avg_conf >= min_confidence:
                        entities.append((' '.join(current_entity), current_cat, avg_conf))
                current_entity = []
                current_cat = None
                current_conf = []

        if current_entity:
            avg_conf = sum(current_conf) / len(current_conf)
            if avg_conf >= min_confidence:
                entities.append((' '.join(current_entity), current_cat, avg_conf))

        LABEL_TO_CATEGORY = {
            "CAST": "Cast", "EXTRAS": "Extras", "STUNTS": "Stunts",
            "VEHICLES": "Vehicles", "PROPS": "Props",
            "SPECIAL_FX": "Special FX", "MAKEUP": "Makeup",
            "SOUND": "Sound", "SET_DRESSING": "Set Dressing",
            "SPECIAL_EQUIPMENT": "Special Equipment", "VFX": "VFX",
        }

        results = []
        for entity_name, label, conf in entities[:max_results]:
            category = LABEL_TO_CATEGORY.get(label, label)
            results.append(SceneElement(
                category=category,
                element_name=entity_name.title(),
                ai_suggested=1,
                ai_confidence=round(conf, 4),
                detection_method="onnx_ner",
            ))

        return results


class DummyInference:
    def predict(self, text, max_results=5, min_confidence=0.30):
        return []
try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False


class BasePDFExporter:
    def __init__(self, project_title=''):
        self._title = project_title

    def _make_pdf(self, orientation='L'):
        pdf = FPDF(orientation=orientation, unit='mm', format='A4')
        pdf.set_margins(10, 15, 10)
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        return pdf

    def _header(self, pdf, subtitle):
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(10, 36, 82)
        pdf.cell(0, 8, 'GLIAMISPO', ln=True)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 6, f'{self._title}  —  {subtitle}', ln=True)
        pdf.ln(4)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
        pdf.ln(4)


class OneLinerExporter(BasePDFExporter):
    def export(self, rows):
        '''rows: lista di tuple (day, num, ie, dn, loc, pages, cast, synopsis)'''
        if not HAS_FPDF:
            return None
        pdf = self._make_pdf('L')   # landscape
        self._header(pdf, 'One-Liner Schedule')
        cols = [
            ('G', 8), ('N°', 12), ('INT/EXT', 18), ('G/N', 18),
            ('Location', 42), ('Pag.', 14), ('Cast', 54), ('Sinossi', 0),
        ]
        # Intestazione
        pdf.set_fill_color(26, 82, 118)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 8)
        for name, w in cols:
            eff_w = w if w else (
                pdf.w - pdf.l_margin - pdf.r_margin
                - sum(c[1] for c in cols if c[1])
            )
            pdf.cell(eff_w, 6, name, border=0, fill=True)
        pdf.ln()
        # Righe
        pdf.set_text_color(0, 0, 0)
        for i, row in enumerate(rows):
            pdf.set_fill_color(244, 246, 246 if i % 2 else 255, 255)
            pdf.set_font('Helvetica', '', 7)
            fill = i % 2 == 0
            pdf.set_fill_color(*(  (244, 246, 246) if fill else (255, 255, 255)  ))
            for (_, w), val in zip(cols, row):
                eff_w = w if w else (
                    pdf.w - pdf.l_margin - pdf.r_margin
                    - sum(c[1] for c in cols if c[1])
                )
                text = str(val) if val else ''
                pdf.cell(eff_w, 5, text[:40], border=0, fill=fill)
            pdf.ln()
        return pdf.output()


class DayOutOfDaysExporter(BasePDFExporter):
    def export(self, cast_names, day_nums, matrix):
        if not HAS_FPDF:
            return None
        pdf = self._make_pdf('L')
        self._header(pdf, 'Day Out of Days')
        col_w   = 8
        actor_w = 50
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_fill_color(26, 82, 118)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(actor_w, 6, 'Attore', fill=True)
        for d in day_nums:
            pdf.cell(col_w, 6, f'G{d}', fill=True, align='C')
        pdf.ln()
        COLORS = {
            'W': (30, 132, 73), 'T': (183, 149, 11),
            'H': (112, 123, 124), 'F': (146, 43, 33),
        }
        pdf.set_text_color(0)
        for i, actor in enumerate(cast_names):
            fill_bg = (244, 246, 246) if i % 2 else (255, 255, 255)
            pdf.set_fill_color(*fill_bg)
            pdf.set_font('Helvetica', '', 7)
            pdf.cell(actor_w, 5, actor[:24], fill=True)
            for d in day_nums:
                status = matrix.get(actor, {}).get(d, '')
                if status and status in COLORS:
                    pdf.set_fill_color(*COLORS[status])
                    pdf.set_text_color(255)
                else:
                    pdf.set_fill_color(*fill_bg)
                    pdf.set_text_color(0)
                pdf.cell(col_w, 5, status, align='C', fill=True)
            pdf.ln()
        return pdf.output()

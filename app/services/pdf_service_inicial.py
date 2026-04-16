"""
Generador de Boleta de Notas INICIAL usando fpdf2.
Layout similar a primaria pero adaptado para nivel inicial (3, 4, 5 años).
Dimensiones en mm. Ancho útil A4 = 190 mm.
"""
import unicodedata
from fpdf import FPDF

from app.services.boleta_staff_service import DEFAULT_DIRECTOR_GENERAL


def _normalize(s: str) -> str:
    """Normaliza un nombre de curso: quita tildes, espacios extra, pasa a mayúsculas."""
    s = s.strip().upper()
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

# ── Paleta de colores ──────────────────────────────────────────────────────────
BRAND       = (14,  47, 119)   # #0e2f77
BIM_BLUE    = (68, 114, 196)   # #4472c4
SUB_BLUE    = (141, 180, 226)  # #8db4e2
AREA_BG     = (214, 228, 240)  # #d6e4f0
PROM_BG     = (220, 230, 241)  # #dce6f1
WHITE       = (255, 255, 255)
BLACK       = (0,   0,   0)
GRAY        = (130, 130, 130)
LIGHT_GRAY  = (210, 210, 210)

BADGE = {
    'AD': {'bg': (219, 234, 254), 'fg': (30,  64, 175)},
    'A':  {'bg': (220, 252, 231), 'fg': (22, 101,  52)},
    'B':  {'bg': (254, 249, 195), 'fg': (113, 63,  18)},
    'C':  {'bg': (254, 226, 226), 'fg': (153, 27,  27)},
}

# ── Constantes de layout ───────────────────────────────────────────────────────
ML   = 8       # margen izquierdo
PW   = 194     # ancho útil (mm)
RH   = 4.6     # balance legibilidad vs 1 hoja A4
HR1  = 5.5     # alto fila header bimestre
HR2  = 4.2     # alto fila sub-header P1/P2

# Columnas tabla de notas (más ancho PF/NL; P1/P2 ligeramente más estrechos)
AW   = 17      # área (mergeada)
CW   = 33      # asignatura
P1W  = 7       # EDA 1
P2W  = 7       # EDA 2
PMW  = 9       # promedio bimestral numérico
QW   = 7       # cualitativo bimestral (letra)
BW   = P1W + P2W + PMW + QW   # = 30 por bimestre
PFW  = 11      # promedio final
NLW  = PW - AW - CW - 4 * BW - PFW   # nivel de logro (~13 mm)

# ── Orden exacto de la boleta INICIAL ──────────────────────────────────────────
BOLETA_LAYOUT = [
    ("COMUNICACIÓN",          ["COMUNICACIÓN", "RAZ. VERBAL", "PLAN LECTOR"]),
    ("MATEMÁTICAS",           ["MATEMÁTICA", "RAZ. MATEMÁTICO"]),
    ("PERSONAL SOCIAL",       ["PERSONAL SOCIAL"]),
    ("CIENCIA Y\nTECNOLOGÍA", ["CIENCIA Y TECNOLOGÍA"]),
    ("EDUCACIÓN RELIGIOSA",   ["EDUCACIÓN RELIGIOSA"]),
    ("EDUCACIÓN FÍSICA",      ["ED. FISICA"]),
    ("ARTE Y CULTURA",        ["ARTE Y CULTURA"]),
    ("INGLÉS",                ["INGLÉS"]),
]


class BoletaInicialPDF(FPDF):

    def __init__(self):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.set_margins(ML, 6, ML)
        self.set_auto_page_break(auto=True, margin=4)

    @staticmethod
    def _safe(text) -> str:
        if text is None:
            return '-'
        text = str(text)
        _MAP = {
            '\u2014': '-', '\u2013': '-', '\u2026': '...',
            '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
            '\u00b0': chr(0xb0), '\u00ab': '<<', '\u00bb': '>>',
        }
        for src, dst in _MAP.items():
            text = text.replace(src, dst)
        return text.encode('latin-1', errors='replace').decode('latin-1')

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _fc(self, rgb): self.set_fill_color(*rgb)
    def _tc(self, rgb): self.set_text_color(*rgb)
    def _dc(self, rgb): self.set_draw_color(*rgb)
    def _reset(self):   self._fc(WHITE); self._tc(BLACK); self._dc(BLACK)

    def _hcell(self, w, h, txt, *, bg=BRAND, fg=WHITE, size=7,
               bold=True, align='C', nx='RIGHT', ny='LAST'):
        self.set_font('Helvetica', 'B' if bold else '', size)
        self._fc(bg); self._tc(fg)
        self.cell(w, h, self._safe(txt), border=1, align=align,
                  fill=True, new_x=nx, new_y=ny)
        self._reset()

    def _dcell(self, w, h, txt, *, bg=WHITE, fg=BLACK, size=7,
               bold=False, align='C', nx='RIGHT', ny='LAST', border=1):
        self.set_font('Helvetica', 'B' if bold else '', size)
        self._fc(bg); self._tc(fg)
        self.cell(w, h, self._safe(txt),
                  border=border, align=align, fill=True, new_x=nx, new_y=ny)
        self._reset()

    def _badge(self, w, h, qual, *, nx='RIGHT', ny='LAST', size=8.5):
        if qual and qual in BADGE:
            b = BADGE[qual]
            self.set_font('Helvetica', 'B', size)
            self._fc(b['bg']); self._tc(b['fg'])
            self.cell(w, h, qual, border=1, align='C',
                      fill=True, new_x=nx, new_y=ny)
        else:
            self.set_font('Helvetica', '', size)
            self._fc(WHITE); self._tc(GRAY)
            self.cell(w, h, '-', border=1, align='C',
                      fill=True, new_x=nx, new_y=ny)
        self._reset()

    def _draw_area_cell(self, x, y, w, h, text):
        sx, sy = self.get_x(), self.get_y()
        self._fc(AREA_BG); self._dc(BLACK)
        self.rect(x, y, w, h, 'DF')
        self.set_font('Helvetica', 'B', 7.5)
        self._tc(BLACK)
        lines = self._safe(text).split('\n')
        line_h = 4.2
        total_h = len(lines) * line_h
        start_y = y + (h - total_h) / 2
        for i, line in enumerate(lines):
            self.set_xy(x, start_y + i * line_h)
            self.cell(w, line_h, line, align='C')
        self._reset()
        self.set_xy(sx, sy)

    def _section_bar(self, title):
        self.set_font('Helvetica', 'B', 7.5)
        self._fc(BRAND); self._tc(WHITE)
        self.cell(PW, 4.2, self._safe(title), border=1, align='C',
                  fill=True, new_x='LMARGIN', new_y='NEXT')
        self._reset()

    def _nl(self, h=RH):
        self.set_x(ML)
        self.set_y(self.get_y() + h)

    # ==========================================================================
    # SECCIONES
    # ==========================================================================

    def _header(self, anio):
        """Encabezado compacto (1 hoja A4)."""
        self.set_font('Helvetica', 'I', 5.5)
        self._tc(GRAY)
        self.cell(PW, 2.6,
                  self._safe('"Ano de la Esperanza y el Fortalecimiento de la Democracia"'),
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self._reset()

        y0 = self.get_y()
        logo_sz = 13.5
        import os
        logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'logosancarlos.png')
        if os.path.exists(logo_path):
            self.image(logo_path, ML, y0, logo_sz, logo_sz)
        else:
            self._dc(BRAND)
            self.rect(ML, y0, logo_sz, logo_sz)

        tx = ML + logo_sz + 1.5
        tw = ML + PW - tx
        self.set_xy(tx, y0 + 0.2)
        self.set_font('Helvetica', 'B', 10)
        self._tc(BRAND)
        self.cell(tw, 3.8, self._safe('INSTITUCION EDUCATIVA'),
                  align='C', new_x='LMARGIN', new_y='NEXT')

        self.set_x(tx)
        self.set_font('Helvetica', 'BI', 12.5)
        self.cell(tw, 4.2, '"San Carlos"',
                  align='C', new_x='LMARGIN', new_y='NEXT')

        self.set_x(tx)
        self.set_font('Helvetica', 'I', 5.8)
        self._tc(GRAY)
        self.cell(tw, 2.6, self._safe('"Nuestra Mision, ... Tu Exito...!"'),
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self._reset()

        self.set_y(y0 + logo_sz + 0.6)
        self.ln(0.3)

    def _student_info(self, student, anio):
        grado_map = {
            '3': '3 AÑOS', '4': '4 AÑOS', '5': '5 AÑOS',
        }
        grado_txt = grado_map.get(str(student.grado), f'{student.grado} AÑOS')

        self.set_font('Helvetica', 'B', 9)
        self._fc(BRAND); self._tc(WHITE)
        self.cell(PW, 4.8,
                  self._safe(f'INFORME ACADEMICO: {grado_txt} DE INICIAL'),
                  border=1, align='C', fill=True, new_x='LMARGIN', new_y='NEXT')
        self._reset()

        lw, h = 38, 4.4

        def row(label, value, bold_val=True):
            self._hcell(lw, h, label, size=8, align='L',
                        bg=AREA_BG, fg=BLACK, nx='RIGHT', ny='LAST')
            self._dcell(PW - lw, h, value, bold=bold_val,
                        size=8.5, nx='LMARGIN', ny='NEXT')

        row('PERIODO DE INFORME :', self._safe(f'ANO LECTIVO {anio}'))
        row('CODIGO DEL ALUMNO :', student.codigo or '')
        row('NOMBRE DEL ALUMNO :', (student.full_name or '').upper())
        self.ln(0.4)

    def _grades_table(self, ctx):
        matrix   = ctx['matrix']
        terms    = ctx['terms']
        eda_data = ctx['eda_data']
        nt = len(terms)
        bim_names = ['I BIMESTRE', 'II BIMESTRE', 'III BIMESTRE', 'IV BIMESTRE']

        name_index: dict[str, tuple] = {}
        for cid, data in matrix.items():
            name_index[_normalize(data['course'].nombre)] = (cid, data)

        y0 = self.get_y()
        y_row2 = y0 + HR1
        y_data = y0 + HR1 + HR2

        self.set_xy(ML, y0)
        self._hcell(AW, HR1 + HR2, 'AREAS', size=8)
        self._hcell(CW, HR1 + HR2, 'ASIGNATURAS', size=8, align='L')

        x_bim = ML + AW + CW
        self.set_xy(x_bim, y0)
        for i in range(nt):
            self._hcell(BW, HR1, bim_names[i] if i < 4 else terms[i].nombre.upper(),
                        bg=BIM_BLUE, size=8)

        x_pf = x_bim + nt * BW
        self.set_xy(x_pf, y0)
        self._hcell(PFW, HR1 + HR2, '', size=8)
        self._hcell(NLW, HR1 + HR2, 'NIVEL DE\nLOGRO', size=6.5)

        self.set_xy(x_bim, y_row2)
        for i in range(nt):
            base = i * 2 + 1
            self._hcell(P1W, HR2, f'P{base}',   bg=SUB_BLUE, fg=BLACK, size=7.5)
            self._hcell(P2W, HR2, f'P{base+1}', bg=SUB_BLUE, fg=BLACK, size=7.5)
            self._hcell(PMW, HR2, 'PROM',        bg=SUB_BLUE, fg=BLACK, size=7.5)
            self._hcell(QW,  HR2, '',             bg=SUB_BLUE, fg=BLACK, size=7.5)

        self.set_xy(ML, y_data)

        rendered_cids: set[int] = set()
        for area_display, course_names in BOLETA_LAYOUT:
            found = []
            for cn in course_names:
                key = _normalize(cn)
                if key in name_index:
                    found.append(name_index[key])

            if not found:
                continue

            n = len(found)
            y_area = self.get_y()

            if n == 1:
                cid, data = found[0]
                rendered_cids.add(cid)
                self.set_xy(ML, y_area)
                self._dcell(AW + CW, RH, area_display, bg=AREA_BG, bold=True,
                            align='L', size=8)
                self._draw_course_grades_row(cid, data, terms, eda_data)
                self.set_xy(ML, y_area + RH)
            else:
                area_h = n * RH
                self._draw_area_cell(ML, y_area, AW, area_h, area_display)
                for idx, (cid, data) in enumerate(found):
                    rendered_cids.add(cid)
                    row_y = y_area + idx * RH
                    self.set_xy(ML + AW, row_y)
                    self._dcell(CW, RH, data['course'].nombre, align='L', size=8)
                    self._draw_course_grades_row(cid, data, terms, eda_data)
                self.set_xy(ML, y_area + area_h)

        # ── Cursos en el matrix que no estaban en el layout
        for cid, data in matrix.items():
            if cid in rendered_cids:
                continue
            y_area = self.get_y()
            self.set_xy(ML, y_area)
            area_label = (data['course'].area or data['course'].nombre).upper()
            self._dcell(AW + CW, RH, area_label, bg=AREA_BG, bold=True,
                        align='L', size=8)
            self._draw_course_grades_row(cid, data, terms, eda_data)
            self.set_xy(ML, y_area + RH)

        self.ln(1.5)

    def _draw_course_grades_row(self, cid, data, terms, eda_data):
        for term in terms:
            v1 = eda_data.get(term.id, {}).get(1, {}).get(cid)
            v2 = eda_data.get(term.id, {}).get(2, {}).get(cid)
            g  = data['terms'].get(term.id)

            self._dcell(P1W, RH, v1 if v1 is not None else '-', size=8.5)
            self._dcell(P2W, RH, v2 if v2 is not None else '-', size=8.5)

            if g and g.numeric_value is not None:
                self._dcell(PMW, RH, g.numeric_value, bg=PROM_BG, bold=True, size=9)
                self._badge(QW, RH, g.qualitative_grade, size=9)
            else:
                self._dcell(PMW, RH, '-', bg=PROM_BG, size=8.5)
                self._badge(QW, RH, None, size=8.5)

        pf_num = data.get('promedio_num')
        if pf_num is not None:
            self._dcell(PFW, RH, pf_num, bg=PROM_BG, bold=True, size=8)
        else:
            self._dcell(PFW, RH, '-', bg=PROM_BG, size=7.5)

        pq = data.get('promedio_cual', '--')
        self._badge(NLW, RH, pq if pq != '--' else None, size=7.5)

    def _scale_attendance(self, ctx):
        meses   = ctx['meses']
        att_map = ctx['att_by_month']
        tf      = ctx['total_faltas']
        tt      = ctx['total_tardanzas']
        prom_a  = ctx['promedio_anual']

        sw = 52
        aw = PW - sw

        lbl_w = 20
        tot_w = 12
        mw    = round((aw - lbl_w - tot_w) / len(meses), 2)

        y0 = self.get_y()

        # ── Escala
        self._hcell(sw, 4.5, 'ESCALA DE VALORES', nx='LMARGIN', ny='NEXT')
        scale_rows = [
            ('DE 18 A 20', 'LOGRO DESTACADO',  'AD'),
            ('DE 14 A 17', 'LOGRO PREVISTO',    'A'),
            ('DE 11 A 13', 'EN PROCESO',        'B'),
            ('DE 00 A 10', 'EN INICIO',         'C'),
        ]
        for rng, desc, q in scale_rows:
            b = BADGE.get(q, {'bg': WHITE, 'fg': BLACK})
            self._dcell(18, RH, rng, size=7.5)
            self._dcell(sw - 18 - 11, RH, desc, align='L', size=7.5)
            self.set_font('Helvetica', 'B', 7.5)
            self._fc(b['bg']); self._tc(b['fg'])
            self.cell(11, RH, q, border=1, align='C', fill=True,
                      new_x='LMARGIN', new_y='NEXT')
            self._reset()

        # ── Asistencia
        self.set_xy(ML + sw, y0)
        self._hcell(lbl_w, 4.5, 'Meses', align='L', size=7.5)
        for m in meses:
            self._hcell(mw, 4.5, m[0], size=8.5)
        self._hcell(tot_w, 4.5, 'TOTAL', size=8.5, nx='LMARGIN', ny='NEXT')

        for label, getter, total in [('FALTAS', 'faltas', tf),
                                      ('TARDANZAS', 'tardanzas', tt)]:
            self.set_x(ML + sw)
            self._hcell(lbl_w, RH, label, bg=AREA_BG, fg=BLACK,
                        size=8.5, align='L')
            for m in meses:
                a   = att_map.get(m)
                val = getattr(a, getter, 0) if a else 0
                self._dcell(mw, RH, f'{val:02d}', size=8.5)
            self._dcell(tot_w, RH, f'{total:02d}', bg=AREA_BG,
                        bold=True, size=8.5, nx='LMARGIN', ny='NEXT')

        # ── Situación final: debajo de TARDANZAS
        y_prom = y0 + 4.5 + RH + RH + 0.6
        x_att = ML + sw
        h_box = 10.0
        if prom_a is not None and prom_a >= 11:
            txt = 'Promovido'
            fill_rgb = (220, 252, 231)
            text_rgb = (21, 128, 61)
        elif prom_a is not None:
            txt = 'No Promovido'
            fill_rgb = (254, 226, 226)
            text_rgb = (153, 27, 27)
        else:
            txt = 'En Proceso'
            fill_rgb = (254, 249, 195)
            text_rgb = (113, 63, 18)

        self._dc(BRAND)
        self.set_fill_color(*fill_rgb)
        self.rect(x_att, y_prom, aw, h_box, style='DF')
        self.set_font('Helvetica', 'BI', 15)
        self._tc(text_rgb)
        self.set_xy(x_att, y_prom + 2.0)
        self.cell(aw, h_box - 2.4, self._safe(txt), align='C',
                  new_x='LMARGIN', new_y='NEXT')
        self._reset()

        scale_h = 4.5 + RH * 4
        att_h   = 4.5 + RH * 2 + 0.6 + h_box
        self.set_y(y0 + max(scale_h, att_h) + 2)
        self.ln(1)

    def _behavior_ppff_row(self, ctx):
        GAP = 2.0
        w_half = (PW - GAP) / 2.0
        xL = ML
        xR = ML + w_half + GAP
        rh = 3.0
        terms = ctx['terms']
        nt = max(len(terms), 1)
        bim_labels = ['I BIM', 'II BIM', 'III BIM', 'IV BIM']
        meses = ctx.get('meses', [])
        mes_labels = [m[:3].upper() for m in meses]

        y0 = self.get_y()
        self.set_font('Helvetica', 'B', 5.5)
        self._fc(BRAND); self._tc(WHITE)
        self.set_xy(xL, y0)
        self.multi_cell(
            PW, 2.35,
            self._safe('EVALUACION DEL COMPORTAMIENTO DEL ALUMNO(A) DENTRO DE LA I.E.'),
            border=1, align='C', fill=True)
        self._reset()
        y1 = self.get_y()

        y_end_L = self._behavior_panel(ctx, xL, PW, y1, rh, meses, mes_labels)
        self.set_y(y_end_L)
        self.ln(0.4)

        # PPFF panel below
        y2 = self.get_y()
        self.set_font('Helvetica', 'B', 5.5)
        self._fc(BRAND); self._tc(WHITE)
        self.set_xy(xL, y2)
        self.multi_cell(
            w_half, 2.35,
            self._safe('EVALUACION DE RESPONSABILIDAD\nDEL PPFF O APODERADO'),
            border=1, align='C', fill=True)
        self._reset()
        y3 = self.get_y()
        y_end_R = self._ppff_panel(ctx, xL, w_half, y3, rh, terms, nt, bim_labels)
        self.set_y(y_end_R)
        self.ln(0.4)

    def _behavior_panel(self, ctx, x0, w, y0, rh, meses, mes_labels):
        indicadores  = ctx['indicadores']
        behavior_bm  = ctx.get('behavior_by_month', {})
        beh_prom     = ctx.get('behavior_monthly_avg', {})
        beh_ind_avgs = ctx.get('behavior_monthly_ind_avgs', {})
        nm = len(meses) if meses else 10
        q_w, prom_w = 6.0, 7.0
        ind_w = min(22, max(16, int(w * 0.16)))
        mes_w = (w - ind_w - prom_w - q_w) / nm
        if mes_w < 5.0:
            ind_w = max(14, w - prom_w - q_w - 5.0 * nm)
            mes_w = (w - ind_w - prom_w - q_w) / nm
        fs, fsh = 4.5, 5.0
        y = y0
        self.set_xy(x0, y)
        self._hcell(ind_w, rh, '', size=fsh)
        for label in mes_labels:
            self._hcell(mes_w, rh, label, size=fsh)
        self._hcell(prom_w, rh, 'PROM.', size=fsh)
        self._hcell(q_w, rh, '', size=fsh, nx='RIGHT', ny='NEXT')
        y = self.get_y()

        for ind in indicadores:
            self.set_xy(x0, y)
            self.set_font('Helvetica', 'B', fs)
            self._fc(AREA_BG); self._tc(BRAND)
            self.cell(ind_w, rh, self._safe(' ' + ind), border=1, align='L',
                      fill=True, new_x='RIGHT', new_y='LAST')
            self._reset()
            for mes in meses:
                month_beh = behavior_bm.get(mes, {})
                b = month_beh.get(ind)
                cal = b.calificacion if b and b.calificacion is not None else None
                self._dcell(mes_w, rh, str(cal) if cal is not None else '-',
                            bold=cal is not None, size=fs)
            ind_avg = beh_ind_avgs.get(ind, {})
            pn = ind_avg.get('promedio_num')
            pq = ind_avg.get('promedio_cual', '--')
            self._dcell(prom_w, rh, str(pn) if pn is not None else '-',
                        bg=PROM_BG, bold=pn is not None, size=fs)
            self._badge(q_w, rh, pq if pq != '--' else None, size=7, nx='RIGHT', ny='NEXT')
            self._reset()
            y = self.get_y()

        self.set_xy(x0, y)
        self.set_font('Helvetica', 'B', fs)
        self._fc(AREA_BG); self._tc(BLACK)
        self.cell(ind_w, rh, self._safe('PROM. GRAL'), border=1,
                  align='R', fill=True, new_x='RIGHT', new_y='LAST')
        self._reset()
        for _ in meses:
            self._dcell(mes_w, rh, '-', size=fs)
        pn = beh_prom.get('promedio_num')
        pq = beh_prom.get('promedio_cual', '--')
        self._dcell(prom_w, rh, str(pn) if pn is not None else '-',
                    bg=PROM_BG, bold=pn is not None, size=fs)
        self._badge(q_w, rh, pq if pq != '--' else None, size=7, nx='RIGHT', ny='NEXT')
        self._reset()
        return self.get_y()

    def _ppff_panel(self, ctx, x0, w, y0, rh, terms, nt, bim_labels):
        indicadores = ctx.get('indicadores_ppff', ['Reuniones', 'Colabora', 'Normas'])
        ppff_bt = ctx.get('ppff_by_term', {})
        ppff_ind_avgs = ctx.get('ppff_ind_avgs', {})
        desc_map = {
            'Reuniones': 'Asiste a las reuniones del plantel.',
            'Colabora':  'Es responsable con su hijo(a).',
            'Normas':    'Respeta el Reglamento Interno.',
        }
        q_w, prom_w = 6.0, 7.0
        desc_w = min(44, max(28, int(w * 0.44)))
        bim_w = (w - desc_w - prom_w - q_w) / nt
        if bim_w < 7.5:
            desc_w = max(24, w - prom_w - q_w - 7.5 * nt)
            bim_w = (w - desc_w - prom_w - q_w) / nt
        fs_bar = 5.5
        line_h = 2.35
        pad = 0.45
        rh_head = rh
        y = y0
        self.set_xy(x0, y)
        self._hcell(desc_w, rh_head, 'Criterio', size=fs_bar, align='R')
        for i in range(len(terms)):
            self._hcell(bim_w, rh_head, bim_labels[i] if i < 4 else '', size=fs_bar)
        self._hcell(prom_w, rh_head, 'PROM.', size=fs_bar)
        self._hcell(q_w, rh_head, '', size=fs_bar, nx='RIGHT', ny='NEXT')
        y = self.get_y()

        for ind in indicadores:
            desc = desc_map.get(ind, ind)
            y_row = y
            self.set_font('Helvetica', 'B', fs_bar)
            lines = self.multi_cell(
                desc_w - 2 * pad, line_h, self._safe(desc),
                split_only=True)
            n = max(1, len(lines))
            h_criterio = max(rh, n * line_h + 2 * pad)

            self._fc(WHITE); self._dc(BLACK)
            self.rect(x0, y_row, desc_w, h_criterio, style='DF')
            self.set_xy(x0 + pad, y_row + pad)
            self.set_font('Helvetica', 'B', fs_bar)
            self._tc(BLACK)
            self.multi_cell(
                desc_w - 2 * pad, line_h, self._safe(desc),
                border=0, align='R')
            self._reset()

            self.set_xy(x0 + desc_w, y_row)
            for term in terms:
                p = ppff_bt.get(term.id, {}).get(ind)
                cal = p.calificacion if p and p.calificacion is not None else None
                self._dcell(bim_w, h_criterio, str(cal) if cal is not None else '-',
                            bold=cal is not None, size=fs_bar)
            ind_avg = ppff_ind_avgs.get(ind, {})
            pn = ind_avg.get('promedio_num')
            pq = ind_avg.get('promedio_cual', '--')
            self._dcell(prom_w, h_criterio, str(pn) if pn is not None else '-',
                        bg=PROM_BG, bold=pn is not None, size=fs_bar)
            self._badge(q_w, h_criterio, pq if pq != '--' else None, size=7,
                        nx='RIGHT', ny='NEXT')
            self._reset()
            y = y_row + h_criterio
            self.set_xy(x0, y)
        return y

    def _comments(self, ctx):
        terms    = ctx['terms']
        comments = ctx['comments_per_term']
        if not terms:
            return

        bim_names = ['I BIMESTRE', 'II BIMESTRE', 'III BIMESTRE', 'IV BIMESTRE']
        lw = 42

        self._section_bar('RECOMENDACIONES DE PARTE DEL TUTOR(A) EN CADA BIMESTRE')

        for i, term in enumerate(terms):
            label = f'Comentarios del {bim_names[i] if i < 4 else term.nombre}'
            text  = comments.get(term.id) or '-'
            self._hcell(lw, RH + 0.5, label, bg=AREA_BG, fg=BLACK,
                        size=7.5, nx='RIGHT', ny='LAST')
            self.set_font('Helvetica', 'I', 7.5)
            self._fc(WHITE); self._tc(BLACK)
            self.cell(PW - lw, RH + 0.5, self._safe(text[:130]), border=1,
                      fill=True, new_x='LMARGIN', new_y='NEXT')
            self._reset()

        self.ln(17)

    def _sig_line(self, sw: float, text: str, placeholder: str) -> None:
        disp = text.strip() if text and text.strip() else placeholder
        n = len(disp)
        fs = 8 if n < 26 else (7 if n < 40 else 6)
        self.set_font('Helvetica', 'B', fs)
        self._tc(BLACK)
        self.cell(sw, 4, self._safe(disp[:90]), align='C', new_x='RIGHT', new_y='LAST')

    def _signatures(self, ctx: dict):
        sw = PW / 3
        line = "____________________________"
        fb = ctx.get("firma_boleta") or {}
        coord = (fb.get("coordinador") or "").strip()
        tutor = (fb.get("tutor") or "").strip()
        st = ctx["student"]
        coord_lbl = "COORDINADOR(A)" if st.nivel == "SECUNDARIA" else "COORDINADORA"
        self.ln(4)
        self.set_x(ML)
        self._sig_line(sw, coord, line)
        self._sig_line(sw, (fb.get("director") or "").strip() or DEFAULT_DIRECTOR_GENERAL, line)
        self._sig_line(sw, tutor, line)
        self.set_x(ML); self.set_y(self.get_y() + 4)

        self.set_font('Helvetica', 'B', 7.5)
        self._tc(BRAND)
        for role in (coord_lbl, "DIRECTOR GENERAL", "TUTOR DE AULA"):
            self.cell(sw, 4, role, align='C', new_x='RIGHT', new_y='LAST')
        self._reset()
        self.set_x(ML); self.set_y(self.get_y() + 4)

    # ==========================================================================
    # ENTRY POINTS
    # ==========================================================================
    def _render(self, ctx: dict):
        self._header(ctx['anio'])
        self._student_info(ctx['student'], ctx['anio'])
        self._grades_table(ctx)
        self._scale_attendance(ctx)
        self._behavior_ppff_row(ctx)
        self._comments(ctx)
        self._signatures(ctx)

    def build(self, ctx: dict) -> bytes:
        self.add_page()
        self._render(ctx)
        return bytes(self.output())

    def build_bulk(self, ctx_list: list) -> bytes:
        for ctx in ctx_list:
            self.add_page()
            self._render(ctx)
        return bytes(self.output())


# ── Funciones públicas ─────────────────────────────────────────────────────────
def generate_boleta_inicial_pdf(ctx: dict) -> bytes:
    return BoletaInicialPDF().build(ctx)


def generate_bulk_boletas_inicial_pdf(ctx_list: list) -> bytes:
    return BoletaInicialPDF().build_bulk(ctx_list)

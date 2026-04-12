"""
Generador de Boleta de Notas PRIMARIA usando fpdf2.
Todas las dimensiones en milímetros. Ancho útil A4 = 190 mm.
"""
from collections import OrderedDict
from fpdf import FPDF

from app.services.boleta_staff_service import DEFAULT_DIRECTOR_GENERAL

# ── Paleta de colores ──────────────────────────────────────────────────────────
BRAND       = (14,  47, 119)   # #0e2f77
BIM_BLUE    = (68, 114, 196)   # #4472c4
SUB_BLUE    = (141, 180, 226)  # #8db4e2
AREA_BG     = (214, 228, 240)  # #d6e4f0
PROM_BG     = (220, 230, 241)  # #dce6f1
ROW_ALT     = (238, 244, 251)
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
ML   = 10      # margen izquierdo/derecho
PW   = 190     # ancho útil (mm)
RH   = 3.6     # alto fila datos
HR1  = 4.5     # alto fila header bimestre
HR2  = 3.5     # alto fila sub-header P1/P2

# Anchos de columna para tabla de notas
AW   = 18      # área (mergeada)
CW   = 34      # asignatura
P1W  = 8       # EDA 1
P2W  = 8       # EDA 2
PMW  = 10      # promedio bimestral
BW   = P1W + P2W + PMW   # = 26 por bimestre
PFW  = 10      # promedio final
NLW  = PW - AW - CW - 4 * BW - PFW   # = 24 nivel de logro

# ── Orden y display de áreas ──────────────────────────────────────────────────
AREA_ORDER = [
    "Comunicación", "Matemática", "Personal Social",
    "Ciencia y Tecnología", "Educación Religiosa",
    "Educación Física", "Arte y Cultura", "Idioma Inglés",
    "Informática", "Tutoría",
]

AREA_DISPLAY = {
    "Comunicación":         "COMUNICACIÓN",
    "Matemática":           "MATEMÁTICAS",
    "Personal Social":      "PERSONAL SOCIAL",
    "Ciencia y Tecnología": "CIENCIA Y\nTECNOLOGÍA",
    "Educación Religiosa":  "EDUCACIÓN RELIGIOSA",
    "Educación Física":     "EDUCACIÓN FÍSICA",
    "Arte y Cultura":       "ARTE Y CULTURA",
    "Idioma Inglés":        "IDIOMA INGLÉS",
    "Informática":          "INFORMÁTICA",
    "Tutoría":              "TUTORÍA",
}


# ── Clase principal ────────────────────────────────────────────────────────────
class BoletaPDF(FPDF):

    def __init__(self):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.set_margins(ML, ML, ML)
        self.set_auto_page_break(auto=True, margin=8)

    # ── Normalización de texto (fuentes core = solo Latin-1) ──────────────────
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

    # ── Helpers de color ───────────────────────────────────────────────────────
    def _fc(self, rgb): self.set_fill_color(*rgb)
    def _tc(self, rgb): self.set_text_color(*rgb)
    def _dc(self, rgb): self.set_draw_color(*rgb)
    def _reset(self):   self._fc(WHITE); self._tc(BLACK); self._dc(BLACK)

    # ── Celda de encabezado ──────────────────────────────────────────────────
    def _hcell(self, w, h, txt, *, bg=BRAND, fg=WHITE, size=5.5,
               bold=True, align='C', nx='RIGHT', ny='LAST'):
        self.set_font('Helvetica', 'B' if bold else '', size)
        self._fc(bg); self._tc(fg)
        self.cell(w, h, self._safe(txt), border=1, align=align,
                  fill=True, new_x=nx, new_y=ny)
        self._reset()

    # ── Celda de datos ───────────────────────────────────────────────────────
    def _dcell(self, w, h, txt, *, bg=WHITE, fg=BLACK, size=5.5,
               bold=False, align='C', nx='RIGHT', ny='LAST', border=1):
        self.set_font('Helvetica', 'B' if bold else '', size)
        self._fc(bg); self._tc(fg)
        self.cell(w, h, self._safe(txt),
                  border=border, align=align, fill=True, new_x=nx, new_y=ny)
        self._reset()

    # ── Celda con badge cualitativo ──────────────────────────────────────────
    def _badge(self, w, h, qual, *, nx='RIGHT', ny='LAST'):
        if qual and qual in BADGE:
            b = BADGE[qual]
            self.set_font('Helvetica', 'B', 5.5)
            self._fc(b['bg']); self._tc(b['fg'])
            self.cell(w, h, qual, border=1, align='C',
                      fill=True, new_x=nx, new_y=ny)
        else:
            self.set_font('Helvetica', '', 5.5)
            self._fc(WHITE); self._tc(GRAY)
            self.cell(w, h, '-', border=1, align='C',
                      fill=True, new_x=nx, new_y=ny)
        self._reset()

    # ── Celda de área mergeada verticalmente ─────────────────────────────────
    def _draw_area_cell(self, x, y, w, h, text):
        self._fc(AREA_BG); self._dc(BLACK)
        self.rect(x, y, w, h, 'DF')
        self.set_font('Helvetica', 'B', 5)
        self._tc(BLACK)
        lines = self._safe(text).split('\n')
        line_h = 3.2
        total_h = len(lines) * line_h
        start_y = y + (h - total_h) / 2
        for i, line in enumerate(lines):
            self.set_xy(x, start_y + i * line_h)
            self.cell(w, line_h, line, align='C')
        self._reset()

    # ── Barra de sección ─────────────────────────────────────────────────────
    def _section_bar(self, title):
        self.set_font('Helvetica', 'B', 6.5)
        self._fc(BRAND); self._tc(WHITE)
        self.cell(PW, 5, title, border=1, align='C',
                  fill=True, new_x='LMARGIN', new_y='NEXT')
        self._reset()

    # ── Nueva fila ───────────────────────────────────────────────────────────
    def _nl(self, h=RH):
        self.set_x(ML)
        self.set_y(self.get_y() + h)

    # ==========================================================================
    # SECCIONES
    # ==========================================================================

    def _header(self, anio):
        self.set_font('Helvetica', 'I', 6.5)
        self._tc(GRAY)
        self.cell(PW, 4,
                  self._safe('"Ano de la Esperanza y el Fortalecimiento de la Democracia"'),
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self._reset()

        y0 = self.get_y()

        # Logo
        import os
        logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'logosancarlos.png')
        if os.path.exists(logo_path):
            self.image(logo_path, ML, y0, 18, 18)
        else:
            self._dc(BRAND)
            self.rect(ML, y0, 18, 18)

        tx = ML + 20
        self.set_xy(tx, y0 + 0.5)
        self.set_font('Helvetica', 'B', 12)
        self._tc(BRAND)
        self.cell(150, 6, self._safe('INSTITUCIÓN EDUCATIVA'),
                  align='C', new_x='LMARGIN', new_y='NEXT')

        self.set_x(tx)
        self.set_font('Helvetica', 'BI', 15)
        self.cell(150, 7, '"San Carlos"',
                  align='C', new_x='LMARGIN', new_y='NEXT')

        self.set_x(tx)
        self.set_font('Helvetica', 'I', 7.5)
        self._tc(GRAY)
        self.cell(150, 4, self._safe('"Nuestra Misión, ... Tu Éxito...!"'),
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self._reset()

        lines = ['Av. San Carlos 406', 'Huancayo', 'Telf: 064-233700',
                 'Cel. 972648005']
        self.set_font('Helvetica', '', 5.5)
        self._tc(GRAY)
        for i, line in enumerate(lines):
            self.set_xy(ML + 172, y0 + 1 + i * 4)
            self.cell(18, 4, line, align='R', new_x='LMARGIN', new_y='NEXT')
        self._reset()

        self.set_y(y0 + 20)
        self.ln(1)

    # ──────────────────────────────────────────────────────────────────────────
    def _student_info(self, student, anio):
        grado_map = {
            '1': 'PRIMERO', '2': 'SEGUNDO', '3': 'TERCERO',
            '4': 'CUARTO',  '5': 'QUINTO',  '6': 'SEXTO',
        }
        grado_txt = grado_map.get(str(student.grado), f'{student.grado}')

        self.set_font('Helvetica', 'B', 9)
        self._fc(BRAND); self._tc(WHITE)
        self.cell(PW, 6, f'INFORME ACADEMICO: {grado_txt} DE PRIMARIA',
                  border=1, align='C', fill=True, new_x='LMARGIN', new_y='NEXT')
        self._reset()

        lw, h = 38, 4.5

        def row(label, value, bold_val=True):
            self._hcell(lw, h, label, size=6.5, align='L',
                        bg=AREA_BG, fg=BLACK, nx='RIGHT', ny='LAST')
            self._dcell(PW - lw, h, value, bold=bold_val,
                        size=7, nx='LMARGIN', ny='NEXT')

        row('PERIODO DE INFORME :', f'AÑO LECTIVO {anio}')
        row('CODIGO DEL ALUMNO :', student.codigo or '')
        row('NOMBRE DEL ALUMNO :', (student.full_name or '').upper())
        self.ln(1)

    # ──────────────────────────────────────────────────────────────────────────
    def _grades_table(self, ctx):
        matrix   = ctx['matrix']
        terms    = ctx['terms']
        eda_data = ctx['eda_data']
        nt = len(terms)
        bim_names = ['I BIMESTRE', 'II BIMESTRE', 'III BIMESTRE', 'IV BIMESTRE']

        # ── Header row 1 ────────────────────────────────────────────────────
        self._hcell(AW, HR1 + HR2, 'AREAS', size=5.5)
        self._hcell(CW, HR1 + HR2, 'ASIGNATURAS', size=5.5, align='L')
        for i in range(nt):
            self._hcell(BW, HR1, bim_names[i] if i < 4 else terms[i].nombre.upper(),
                        bg=BIM_BLUE, size=5.5)
        # PF header — draw manually to span 2 rows
        pf_x = self.get_x()
        pf_y = self.get_y()
        self._hcell(PFW, HR1 + HR2, '', size=5.5)
        self._hcell(NLW, HR1 + HR2, 'NIVEL DE\nLOGRO', size=5,
                    nx='LMARGIN', ny='NEXT')

        # ── Header row 2 (sub-headers P1/P2/PROM) ──────────────────────────
        self.set_x(ML + AW + CW)
        for i in range(nt):
            base = i * 2 + 1
            self._hcell(P1W, HR2, f'P{base}',   bg=SUB_BLUE, fg=BLACK, size=5)
            self._hcell(P2W, HR2, f'P{base+1}', bg=SUB_BLUE, fg=BLACK, size=5)
            self._hcell(PMW, HR2, 'PROM',        bg=SUB_BLUE, fg=BLACK, size=5)
        # Skip PF+NL (already drawn spanning 2 rows)
        self.set_x(ML)
        self.set_y(self.get_y() + HR2)

        # ── Group courses by area ───────────────────────────────────────────
        area_courses: OrderedDict[str, list] = OrderedDict()
        for cid, data in matrix.items():
            area = data['course'].area
            area_courses.setdefault(area, []).append((cid, data))

        sorted_areas: OrderedDict[str, list] = OrderedDict()
        for area in AREA_ORDER:
            if area in area_courses:
                sorted_areas[area] = area_courses[area]
        for area in area_courses:
            if area not in sorted_areas:
                sorted_areas[area] = area_courses[area]

        # ── Draw course rows ────────────────────────────────────────────────
        for area, courses in sorted_areas.items():
            n = len(courses)
            area_h = n * RH
            y_area = self.get_y()
            display = AREA_DISPLAY.get(area, area.upper())

            if n == 1:
                # Standalone area: name in combined AW+CW cell
                cid, data = courses[0]
                self._dcell(AW + CW, RH, display, bg=AREA_BG, bold=True,
                            align='L', size=5.5)
                self._draw_course_grades(cid, data, terms, eda_data)
            else:
                # Multi-course: merged area cell
                self._draw_area_cell(ML, y_area, AW, area_h, display)
                for cid, data in courses:
                    self.set_x(ML + AW)
                    self._dcell(CW, RH, data['course'].nombre, align='L', size=5.5)
                    self._draw_course_grades(cid, data, terms, eda_data)

        self.ln(1.5)

    def _draw_course_grades(self, cid, data, terms, eda_data):
        """Draw grade columns for a single course row (P1/P2/PROM per term + PF + NL)."""
        for term in terms:
            v1 = eda_data.get(term.id, {}).get(1, {}).get(cid)
            v2 = eda_data.get(term.id, {}).get(2, {}).get(cid)
            g  = data['terms'].get(term.id)

            self._dcell(P1W, RH, v1 if v1 is not None else '-')
            self._dcell(P2W, RH, v2 if v2 is not None else '-')

            if g and g.numeric_value is not None:
                self._dcell(PMW, RH, g.numeric_value, bg=PROM_BG, bold=True)
            else:
                self._dcell(PMW, RH, '-', bg=PROM_BG)

        # PF (promedio final)
        pf_num = data.get('promedio_num')
        if pf_num is not None:
            self._dcell(PFW, RH, pf_num, bg=PROM_BG, bold=True)
        else:
            self._dcell(PFW, RH, '-', bg=PROM_BG)

        # Nivel de logro
        pq = data.get('promedio_cual', '--')
        self._badge(NLW, RH, pq if pq != '--' else None,
                    nx='LMARGIN', ny='LAST')
        self._nl(RH)

    # ──────────────────────────────────────────────────────────────────────────
    def _scale_attendance(self, ctx):
        meses   = ctx['meses']
        att_map = ctx['att_by_month']
        tf      = ctx['total_faltas']
        tt      = ctx['total_tardanzas']
        prom_a  = ctx['promedio_anual']

        sw = 52    # escala de valores
        pw = 22    # sello promovido
        aw = PW - sw - pw   # asistencia

        lbl_w  = 20
        tot_w  = 12
        mw     = round((aw - lbl_w - tot_w) / len(meses), 2)

        y0 = self.get_y()

        # ── Escala ──────────────────────────────────────────────────────────
        self._hcell(sw, 4.5, 'ESCALA DE VALORES', nx='LMARGIN', ny='NEXT')
        scale_rows = [
            ('DE 18 A 20', 'LOGRO DESTACADO',  'AD'),
            ('DE 14 A 17', 'LOGRO PROGRESIVO', 'A'),
            ('DE 11 A 13', 'EN PROCESO',        'B'),
            ('DE 00 A 10', 'EN INICIO',          'C'),
        ]
        for rng, desc, q in scale_rows:
            b = BADGE.get(q, {'bg': WHITE, 'fg': BLACK})
            self._dcell(18, RH, rng, size=6)
            self._dcell(sw - 18 - 11, RH, desc, align='L', size=6)
            self.set_font('Helvetica', 'B', 6)
            self._fc(b['bg']); self._tc(b['fg'])
            self.cell(11, RH, q, border=1, align='C', fill=True,
                      new_x='LMARGIN', new_y='NEXT')
            self._reset()

        # ── Asistencia ──────────────────────────────────────────────────────
        self.set_xy(ML + sw, y0)
        self._hcell(lbl_w, 4.5, 'Meses', align='L', size=6)
        for m in meses:
            self._hcell(mw, 4.5, m[0], size=5.5)
        self._hcell(tot_w, 4.5, 'TOTAL', size=5.5, nx='LMARGIN', ny='NEXT')

        for label, getter, total in [('FALTAS', 'faltas', tf),
                                      ('TARDANZAS', 'tardanzas', tt)]:
            self.set_x(ML + sw)
            self._hcell(lbl_w, RH, label, bg=AREA_BG, fg=BLACK,
                        size=5.5, align='L')
            for m in meses:
                a   = att_map.get(m)
                val = getattr(a, getter, 0) if a else 0
                self._dcell(mw, RH, f'{val:02d}', size=5.5)
            self._dcell(tot_w, RH, f'{total:02d}', bg=AREA_BG,
                        bold=True, size=5.5, nx='LMARGIN', ny='NEXT')

        # ── Situación final (sin recuadro) ────────────────────────────────
        px = ML + sw + aw
        cy = y0 + 10

        if prom_a is not None and prom_a >= 11:
            plines = ['Promovido']
        elif prom_a is not None:
            plines = ['No Promovido']
        else:
            plines = ['En Proceso']

        self.set_font('Helvetica', 'BI', 7)
        self._tc(BRAND)
        base_y = cy - len(plines) * 3.5 / 2
        for i, ln in enumerate(plines):
            self.set_xy(px, base_y + i * 3.5)
            self.cell(pw, 3.5, ln, align='C', new_x='LMARGIN', new_y='NEXT')
        self._reset()

        # Avanzar Y al máximo entre escala (4 filas) y asistencia (2 filas)
        scale_h = 4.5 + RH * 4
        att_h   = 4.5 + RH * 2
        self.set_y(y0 + max(scale_h, att_h) + 2)
        self.ln(1)

    # ──────────────────────────────────────────────────────────────────────────
    def _behavior(self, ctx):
        indicadores = ctx['indicadores']
        behavior    = ctx['behavior']
        terms       = ctx['terms']

        bim_labels = ['I BIM', 'II BIM', 'III BIM', 'IV BIM']

        rh = 2.8  # fila compacta
        ind_w  = 42
        bim_w  = 20
        nt     = len(terms)
        prom_w = PW - ind_w - nt * bim_w - 12
        q_w    = 12

        # Barra título compacta
        self.set_font('Helvetica', 'B', 5.5)
        self._fc(BRAND); self._tc(WHITE)
        self.cell(PW, 3.5, self._safe('EVALUACION DEL COMPORTAMIENTO DEL ALUMNO(A)'),
                  border=1, align='C', fill=True, new_x='LMARGIN', new_y='NEXT')
        self._reset()

        # Header
        self._hcell(ind_w, rh, '', align='R', size=4.5)
        for i in range(nt):
            self._hcell(bim_w, rh, bim_labels[i] if i < 4 else '', size=4.5)
        self._hcell(prom_w, rh, 'PROM.', size=4.5)
        self._hcell(q_w,    rh, '',      size=4.5, nx='LMARGIN', ny='NEXT')

        for ind in indicadores:
            b = behavior.get(ind)
            self.set_font('Helvetica', 'B', 5)
            self._fc(AREA_BG); self._tc(BRAND)
            self.cell(ind_w, rh, self._safe('  ' + ind), border=1, align='L',
                      fill=True, new_x='RIGHT', new_y='LAST')
            self._reset()
            for _ in range(nt):
                self._dcell(bim_w, rh, '-', size=4.5)
            self._dcell(prom_w, rh, '-', bg=PROM_BG, size=4.5)
            q = b.calificacion if b and b.calificacion else None
            self._badge(q_w, rh, q, nx='LMARGIN', ny='LAST')
            self._nl(rh)

        self.ln(0.5)

    # ──────────────────────────────────────────────────────────────────────────
    def _ppff(self, ctx):
        terms = ctx['terms']
        bim_labels = ['I BIM', 'II BIM', 'III BIM', 'IV BIM']
        criterios  = [
            'Respeta el Reglamento Interno.',
            'Es responsable con su hijo(a).',
            'Asiste a las reuniones del plantel.',
        ]

        rh = 2.8  # fila compacta
        desc_w = 65
        nt     = len(terms)
        bim_w  = 20
        prom_w = PW - desc_w - nt * bim_w - 10
        q_w    = 10

        # Barra título compacta
        self.set_font('Helvetica', 'B', 5.5)
        self._fc(BRAND); self._tc(WHITE)
        self.cell(PW, 3.5, self._safe('EVALUACION DE RESPONSABILIDAD DEL PPFF O APODERADO'),
                  border=1, align='C', fill=True, new_x='LMARGIN', new_y='NEXT')
        self._reset()

        # Header
        self._hcell(desc_w, rh, '', align='R', size=4.5)
        for i in range(nt):
            self._hcell(bim_w, rh, bim_labels[i] if i < 4 else '', size=4.5)
        self._hcell(prom_w, rh, 'PROM.', size=4.5)
        self._hcell(q_w,    rh, '',      size=4.5, nx='LMARGIN', ny='NEXT')

        for desc in criterios:
            self.set_font('Helvetica', 'I', 4.5)
            self._fc(WHITE); self._tc(BLACK)
            self.cell(desc_w, rh, self._safe(desc), border=1, align='R',
                      fill=True, new_x='RIGHT', new_y='LAST')
            self._reset()
            for _ in range(nt):
                self._dcell(bim_w, rh, '-')
            self._dcell(prom_w, rh, '-')
            self._badge(q_w, rh, None, nx='LMARGIN', ny='LAST')
            self._nl(rh)

        self.ln(0.5)

    # ──────────────────────────────────────────────────────────────────────────
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
                        size=6, nx='RIGHT', ny='LAST')
            self.set_font('Helvetica', 'I', 6)
            self._fc(WHITE); self._tc(BLACK)
            self.cell(PW - lw, RH + 0.5, self._safe(text[:130]), border=1,
                      fill=True, new_x='LMARGIN', new_y='NEXT')
            self._reset()

        self.ln(17)

    # ──────────────────────────────────────────────────────────────────────────
    def _sig_line(self, sw: float, text: str, placeholder: str) -> None:
        disp = text.strip() if text and text.strip() else placeholder
        n = len(disp)
        fs = 6.5 if n < 26 else (6 if n < 40 else 5.5)
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
        self.ln(8)
        self.set_x(ML)
        self._sig_line(sw, coord, line)
        self._sig_line(sw, (fb.get("director") or "").strip() or DEFAULT_DIRECTOR_GENERAL, line)
        self._sig_line(sw, tutor, line)
        self.set_x(ML); self.set_y(self.get_y() + 4)

        self.set_font('Helvetica', 'B', 6)
        self._tc(BRAND)
        for role in (coord_lbl, "DIRECTOR GENERAL", "TUTOR DE AULA"):
            self.cell(sw, 4, role, align='C', new_x='RIGHT', new_y='LAST')
        self._reset()
        self.set_x(ML); self.set_y(self.get_y() + 4)

    # ──────────────────────────────────────────────────────────────────────────
    def _footer(self, anio, fecha):
        self.ln(2)
        self._dc(LIGHT_GRAY)
        self.line(ML, self.get_y(), ML + PW, self.get_y())
        self.ln(1)
        self.set_font('Helvetica', '', 5.5)
        self._tc(GRAY)
        self.cell(PW / 2, 4,
                  f'Complejo Educativo SAN CARLOS {anio}  |  Av. San Carlos 406 - Huancayo',
                  align='L', new_x='RIGHT', new_y='LAST')
        self.cell(PW / 2, 4,
                  f'Telf: 064-233700  |  Cel. 972648005  |  {fecha}',
                  align='R', new_x='LMARGIN', new_y='NEXT')
        self._reset()

    # ==========================================================================
    # ENTRY POINTS
    # ==========================================================================
    def _render(self, ctx: dict):
        self._header(ctx['anio'])
        self._student_info(ctx['student'], ctx['anio'])
        self._grades_table(ctx)
        self._scale_attendance(ctx)
        self._behavior(ctx)
        self._ppff(ctx)
        self._comments(ctx)
        self._signatures(ctx)
        self._footer(ctx['anio'], ctx['fecha_emision'])

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
def generate_boleta_pdf(ctx: dict) -> bytes:
    return BoletaPDF().build(ctx)


def generate_bulk_boletas_pdf(ctx_list: list) -> bytes:
    return BoletaPDF().build_bulk(ctx_list)

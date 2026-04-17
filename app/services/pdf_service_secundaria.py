"""
Generador de Boleta de Notas SECUNDARIA usando fpdf2.
Layout fiel a boletasecundaria.jpg:
  - Áreas fusionadas verticalmente
  - Columnas: ÁREA | ASIGNATURA | [P1 P2 PROM]×4 bimestres | PF | NIVEL DE LOGRO
  - Sin filas de total de área
  - Sin cualitativo por bimestre (solo al final)
Dimensiones en mm. Ancho útil A4 = 190 mm.
"""
from collections import OrderedDict
from fpdf import FPDF

from app.services.boleta_staff_service import DEFAULT_DIRECTOR_GENERAL
from app.services.grade_service import _round_half_up, numeric_to_qualitative

# ── Paleta de colores ──────────────────────────────────────────────────────────
BRAND       = (14,  47, 119)
BIM_BLUE    = (68, 114, 196)
SUB_BLUE    = (141, 180, 226)
AREA_BG     = (214, 228, 240)
PROM_BG     = (220, 230, 241)
ROW_ALT     = (238, 244, 251)
WHITE       = (255, 255, 255)
BLACK       = (0,   0,   0)
GRAY        = (130, 130, 130)
LIGHT_GRAY  = (210, 210, 210)

BADGE = {
    'AD': {'bg': (219, 234, 254), 'fg': (30,  64, 175)},
    'A':  {'bg': (219, 234, 254), 'fg': (30,  64, 175)},
    'B':  {'bg': (220, 252, 231), 'fg': (22, 101,  52)},
    'C':  {'bg': (254, 226, 226), 'fg': (153, 27,  27)},
}

# ── Layout constants ───────────────────────────────────────────────────────────
ML   = 8        # margen izq/der
PW   = 194      # ancho útil
RH   = 4.6      # balance legibilidad vs 1 hoja A4
HR1  = 5.5      # alto fila header bimestre
HR2  = 4.2      # alto fila sub-header P1/P2

# Columnas tabla de notas
AW   = 19       # ÁREAS (fusionada verticalmente)
CW   = 37       # ASIGNATURAS
P1W  = 8        # EDA impar (libera espacio para PF / NIVEL DE LOGRO)
P2W  = 8        # EDA par
PMW  = 11       # PROM bimestral
BW   = P1W + P2W + PMW   # = 27 por bimestre
PFW  = 12       # Promedio Final
NLW  = PW - AW - CW - 4 * BW - PFW   # nivel de logro (~19 mm)

# ── Cursos por grado (define orden y agrupación por área en la boleta) ────────
# Cada entrada: (área_display, [lista de nombres de curso])
# El nombre de curso debe coincidir con Course.nombre en la BD.

_CURSOS_1_2 = OrderedDict([
    ("COMUNICACIÓN",        ["LENGUAJE", "LITERATURA", "RAZ. VERBAL", "COMP. LECTORA"]),
    ("MATEMÁTICAS",         ["ARITMÉTICA", "ÁLGEBRA", "GEOMETRÍA", "RAZ. MATEMÁTICO"]),
    ("CIENCIAS\nSOCIALES",  ["HISTORIA UNIVERSAL", "HISTORIA DEL PERÚ", "GEOGRAFÍA", "METODOLOGÍA"]),
    ("CIENCIA Y\nTECNOLOGÍA", ["FÍSICA", "QUÍMICA", "BIOLOGÍA"]),
    ("IDIOMA EXTRANJERO",   ["INGLÉS"]),
    ("DPCC",                ["EDUCACIÓN CIVICA"]),
    ("EDUCACIÓN FÍSICA",    ["EDUCACIÓN FÍSICA"]),
    ("ROBÓTICA",            ["ROBÓTICA"]),
    ("ITALIANO",            ["ITALIANO"]),
])

_CURSOS_3 = OrderedDict([
    ("COMUNICACIÓN",        ["LENGUAJE", "LITERATURA", "RAZ. VERBAL", "COMP. LECTORA"]),
    ("MATEMÁTICAS",         ["ARITMÉTICA", "ÁLGEBRA", "GEOMETRÍA", "TRIGONOMETRÍA", "RAZ. MATEMÁTICO"]),
    ("CIENCIAS\nSOCIALES",  ["HISTORIA UNIVERSAL", "HISTORIA DEL PERÚ", "GEOGRAFÍA", "METODOLOGÍA"]),
    ("CIENCIA Y\nTECNOLOGÍA", ["FÍSICA", "QUÍMICA", "BIOLOGÍA"]),
    ("EDUCACIÓN FÍSICA",    ["EDUCACIÓN FÍSICA"]),
    ("IDIOMA EXTRANJERO",   ["INGLÉS"]),
    ("ROBÓTICA",            ["ROBÓTICA"]),
    ("ITALIANO",            ["ITALIANO"]),
])

_CURSOS_4_5 = OrderedDict([
    ("COMUNICACIÓN",        ["LENGUAJE", "LITERATURA", "RAZ. VERBAL", "COMP. LECTORA"]),
    ("MATEMÁTICAS",         ["ARITMÉTICA", "ÁLGEBRA", "GEOMETRÍA", "TRIGONOMETRÍA", "RAZ. MATEMÁTICO", "ESTADÍSTICA"]),
    ("CIENCIAS\nSOCIALES",  ["HISTORIA DEL PERÚ", "GEOGRAFÍA", "ECONOMÍA"]),
    ("CIENCIA Y\nTECNOLOGÍA", ["FÍSICA", "QUÍMICA", "BIOLOGÍA", "ECOLOGÍA"]),
    ("IDIOMA EXTRANJERO",   ["INGLÉS"]),
    ("DPCC",                ["EDUCACIÓN CIVICA", "FILOSOFÍA", "PSICOLOGÍA"]),
    ("EDUCACIÓN FÍSICA",    ["EDUCACIÓN FÍSICA"]),
    ("ROBÓTICA",            ["ROBÓTICA"]),
    ("ITALIANO",            ["ITALIANO"]),
])

CURSOS_POR_GRADO = {
    "1": _CURSOS_1_2,
    "2": _CURSOS_1_2,
    "3": _CURSOS_3,
    "4": _CURSOS_4_5,
    "5": _CURSOS_4_5,
}

# Fallback: orden y display genéricos (si el grado no está configurado)
AREA_ORDER = [
    "Matemática", "Comunicación", "DPCC", "Ciencias Sociales",
    "Ciencia y Tecnología", "Educación Física", "Idioma Inglés",
]

AREA_DISPLAY = {
    "Matemática":           "MATEMÁTICAS",
    "Comunicación":         "COMUNICACIÓN",
    "DPCC":                 "DPCC",
    "Ciencias Sociales":    "CIENCIAS\nSOCIALES",
    "Ciencia y Tecnología": "CIENCIA Y\nTECNOLOGÍA",
    "Educación Física":     "EDUCACIÓN FÍSICA",
    "Idioma Inglés":        "IDIOMA EXTRANJERO",
}


class BoletaSecundariaPDF(FPDF):

    def __init__(self):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.set_margins(ML, 6, ML)
        self.set_auto_page_break(auto=True, margin=4)

    # ── Texto seguro (solo Latin-1) ──────────────────────────────────────────
    @staticmethod
    def _safe(text) -> str:
        if text is None:
            return '-'
        text = str(text)
        _MAP = {
            '\u2014': '-', '\u2013': '-', '\u2026': '...',
            '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
            '\u00ab': '<<', '\u00bb': '>>',
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

    def _draw_area_final(self, x, y, h, avg, qual):
        """Celda PROMEDIO FINAL fusionada: sub-columna numérica + sub-columna letra."""
        self._fc(PROM_BG); self._dc(BLACK)
        self.rect(x, y, PFW, h, style='DF')
        self.set_font('Helvetica', 'B', 10)
        self._tc(BLACK)
        txt = str(avg) if avg is not None else '-'
        self.set_xy(x, y + (h - 4.2) / 2)
        self.cell(PFW, 4.2, self._safe(txt), align='C')

        if qual and qual in BADGE:
            b = BADGE[qual]
            self._fc(b['bg']); self._dc(BLACK)
            self.rect(x + PFW, y, NLW, h, style='DF')
            self.set_font('Helvetica', 'B', 11)
            self._tc(b['fg'])
            self.set_xy(x + PFW, y + (h - 4.2) / 2)
            self.cell(NLW, 4.2, qual, align='C')
        else:
            self._fc(WHITE); self._dc(BLACK)
            self.rect(x + PFW, y, NLW, h, style='DF')
            self.set_font('Helvetica', '', 9)
            self._tc(GRAY)
            self.set_xy(x + PFW, y + (h - 4.2) / 2)
            self.cell(NLW, 4.2, '-', align='C')
        self._reset()

    def _section_bar(self, title):
        self.set_font('Helvetica', 'B', 7.5)
        self._fc(BRAND); self._tc(WHITE)
        self.cell(PW, 4.2, title, border=1, align='C',
                  fill=True, new_x='LMARGIN', new_y='NEXT')
        self._reset()

    # ── Celda de área fusionada ──────────────────────────────────────────────
    def _draw_area_cell_direct(self, display: str, y: float, h: float):
        """Dibuja la celda de área fusionada usando el nombre display directamente."""
        self._draw_area_cell_impl(display, y, h)

    def _draw_area_cell(self, area_name: str, y: float, h: float):
        """Dibuja la celda de área fusionada verticalmente con texto centrado."""
        display = AREA_DISPLAY.get(area_name, area_name.upper())
        self._draw_area_cell_impl(display, y, h)

    def _draw_area_cell_impl(self, display: str, y: float, h: float):
        """Implementación de la celda de área fusionada con auto-wrap/shrink."""
        self._dc(BLACK)
        self._fc(AREA_BG)
        self.rect(ML, y, AW, h, style='DF')

        def _wrap(txt, max_w, fs):
            self.set_font('Helvetica', 'B', fs)
            out = []
            for raw_ln in txt.split('\n'):
                if self.get_string_width(raw_ln) <= max_w:
                    out.append(raw_ln); continue
                words = raw_ln.split()
                cur = ''
                for word in words:
                    test = f'{cur} {word}'.strip()
                    if self.get_string_width(test) <= max_w:
                        cur = test
                    else:
                        if cur: out.append(cur)
                        cur = word
                if cur: out.append(cur)
            return out

        pad = 1.0
        fs = 7.5
        lines = _wrap(self._safe(display), AW - 2 * pad, fs)
        while fs > 5.0:
            self.set_font('Helvetica', 'B', fs)
            widest = max((self.get_string_width(ln) for ln in lines), default=0)
            fits_h = len(lines) * (fs * 0.48) <= h - 0.4
            fits_w = widest <= AW - 2 * pad
            if fits_h and fits_w:
                break
            fs -= 0.5
            lines = _wrap(self._safe(display), AW - 2 * pad, fs)

        self.set_font('Helvetica', 'B', fs)
        line_h = fs * 0.48
        total_h = len(lines) * line_h
        text_y = y + (h - total_h) / 2

        self._tc(BLACK)
        for i, ln in enumerate(lines):
            self.set_xy(ML, text_y + i * line_h)
            self.cell(AW, line_h, ln, align='C')
        self._reset()

    # =====================================================================
    # HEADER
    # =====================================================================
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
            self._fc(BRAND)
            self.rect(ML, y0, logo_sz, logo_sz, style='DF')
        self._reset()

        tx = ML + logo_sz + 1.5
        tw = ML + PW - tx
        self.set_xy(tx, y0 + 0.2)
        self.set_font('Helvetica', 'B', 10)
        self._tc(BRAND)
        self.cell(tw, 3.8, self._safe('COLEGIO'),
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_x(tx)
        self.set_font('Helvetica', 'BI', 12.5)
        self.cell(tw, 4.2, self._safe('"San Carlos"'),
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_x(tx)
        self.set_font('Helvetica', 'I', 5.8)
        self._tc(GRAY)
        self.cell(tw, 2.6, self._safe('"Nuestra Mision, ... Tu Exito...!"'),
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self._reset()

        self.set_y(y0 + logo_sz + 0.6)
        self.ln(0.3)

    # =====================================================================
    # INFO ESTUDIANTE
    # =====================================================================
    def _student_info(self, student, anio):
        grado_map = {
            '1': 'PRIMERO', '2': 'SEGUNDO', '3': 'TERCERO',
            '4': 'CUARTO',  '5': 'QUINTO',
        }
        grado_txt = grado_map.get(str(student.grado), f'{student.grado}')

        self.set_font('Helvetica', 'B', 9)
        self._fc(BRAND); self._tc(WHITE)
        self.cell(PW, 4.8,
                  self._safe(f'INFORME ACADÉMICO {grado_txt} DE SECUNDARIA'),
                  border=1, align='C', fill=True, new_x='LMARGIN', new_y='NEXT')
        self._reset()

        lw, h = 38, 4.4

        def row(label, value):
            self._hcell(lw, h, label, size=8, align='L',
                        bg=AREA_BG, fg=BLACK, nx='RIGHT', ny='LAST')
            self._dcell(PW - lw, h, value, bold=True,
                        size=8.5, nx='LMARGIN', ny='NEXT')

        row('PERIODO DE INFORME :', self._safe(f'AÑO LECTIVO {anio}'))
        row('CÓDIGO DEL ALUMNO :', student.codigo or '')
        row('ESTUDIANTE :', (student.full_name or '').upper())
        self.ln(0.4)

    # =====================================================================
    # TABLA DE NOTAS
    # =====================================================================
    def _grades_table(self, ctx):
        matrix    = ctx['matrix']
        terms     = ctx['terms']
        eda_data  = ctx['eda_data']
        student   = ctx['student']
        bim_names = ['I BIMESTRE', 'II BIMESTRE', 'III BIMESTRE', 'IV BIMESTRE']

        # ── Índice de cursos por nombre (upper, sin tildes) ──────────────
        def _normalize(name: str) -> str:
            import unicodedata
            nfkd = unicodedata.normalize('NFKD', name.upper())
            return ''.join(c for c in nfkd if not unicodedata.combining(c)).strip()

        course_by_name: dict[str, tuple[int, dict]] = {}
        for course_id, data in matrix.items():
            key = _normalize(data['course'].nombre)
            course_by_name[key] = (course_id, data)

        # ── Obtener configuración de cursos por grado ────────────────────
        grado = str(student.grado)
        cursos_cfg = CURSOS_POR_GRADO.get(grado)

        if cursos_cfg:
            # Construir grupos ordenados según la configuración del grado
            sorted_groups: OrderedDict[str, list] = OrderedDict()
            used_ids: set[int] = set()

            for area_display, curso_names in cursos_cfg.items():
                items = []
                for cn in curso_names:
                    key = _normalize(cn)
                    match = course_by_name.get(key)
                    if match:
                        items.append(match)
                        used_ids.add(match[0])
                if items:
                    sorted_groups[area_display] = items

            # Cursos no configurados para este grado se omiten de la boleta
        else:
            # Fallback: agrupar por área de BD
            area_groups: OrderedDict[str, list] = OrderedDict()
            for course_id, data in matrix.items():
                area = data['course'].area
                area_groups.setdefault(area, []).append((course_id, data))

            sorted_groups = OrderedDict()
            for a in AREA_ORDER:
                if a in area_groups:
                    display = AREA_DISPLAY.get(a, a.upper())
                    sorted_groups[display] = area_groups.pop(a)
            for a, v in area_groups.items():
                display = AREA_DISPLAY.get(a, a.upper())
                sorted_groups[display] = v

        # ── Calcular alto de fila dinámico según cantidad de cursos ──────
        total_courses = sum(len(items) for items in sorted_groups.values())
        rh = 4.0 if total_courses > 20 else (4.3 if total_courses > 18 else RH)

        # ── Fila header superior ─────────────────────────────────────────
        hdr_h = HR1 + HR2
        self._hcell(AW,  hdr_h, self._safe('ÁREAS'), size=9)
        self._hcell(CW,  hdr_h, 'ASIGNATURAS', size=9, align='L')
        for i in range(min(len(terms), 4)):
            self._hcell(BW, HR1, bim_names[i], bg=BIM_BLUE, size=7.5)
        for i in range(4, len(terms)):
            self._hcell(BW, HR1, terms[i].nombre.upper(), bg=BIM_BLUE, size=7.5)
        self._hcell(PFW + NLW, HR1, 'PROMEDIO FINAL', size=7,
                    nx='LMARGIN', ny='NEXT')

        # ── Fila sub-header P1 P2 PROM ───────────────────────────────────
        self.set_x(ML + AW + CW)
        for i in range(len(terms)):
            base = i * 2 + 1
            self._hcell(P1W, HR2, f'P{base}',  bg=SUB_BLUE, fg=BLACK, size=7.5)
            self._hcell(P2W, HR2, f'P{base+1}', bg=SUB_BLUE, fg=BLACK, size=7.5)
            self._hcell(PMW, HR2, 'PROM',       bg=SUB_BLUE, fg=BLACK, size=7.5)
        self._hcell(PFW, HR2, 'PROM',  bg=SUB_BLUE, fg=BLACK, size=7.5)
        self._hcell(NLW, HR2, 'NIVEL', bg=SUB_BLUE, fg=BLACK, size=7.5)
        self.set_x(ML)
        self.set_y(self.get_y() + HR2)

        # ── Filas de cursos por área ─────────────────────────────────────
        for area_display, items in sorted_groups.items():
            n = len(items)
            y_area = self.get_y()
            area_height = n * rh

            # Detectar áreas de un solo curso (Educación Física, Idioma Inglés, etc.)
            single = (n == 1)

            single_merged = False
            if single:
                cid0, cdata0 = items[0]
                course_name0 = cdata0['course'].nombre or ''
                area_norm = area_display.replace('\n', ' ').strip().upper()
                course_norm = course_name0.strip().upper()
                if area_norm == course_norm:
                    # Nombres idénticos: fusionar área + asignatura
                    self._hcell(AW + CW, rh, area_display, bg=AREA_BG, fg=BLACK,
                                size=9, align='L')
                    single_merged = True
                else:
                    # Nombres distintos: área en AW y asignatura en CW
                    self._draw_area_cell_direct(area_display, y_area, rh)
                    self.set_xy(ML + AW, y_area)
                    self._dcell(CW, rh, course_name0, align='L', size=9)

            # Dibujar cada fila de curso (solo notas bimestrales)
            for i, (cid, cdata) in enumerate(items):
                course = cdata['course']
                row_y = y_area + i * rh

                if not single:
                    self.set_xy(ML + AW, row_y)
                    # Celda de curso
                    self._dcell(CW, rh, course.nombre, align='L', size=9)
                elif not single_merged:
                    # El área + curso ya se dibujaron por separado arriba
                    self.set_xy(ML + AW + CW, row_y)
                # else: ya se dibujó la celda combinada, posición correcta

                # Notas por bimestre
                for term in terms:
                    v1 = eda_data.get(term.id, {}).get(1, {}).get(cid)
                    v2 = eda_data.get(term.id, {}).get(2, {}).get(cid)
                    g  = cdata['terms'].get(term.id)

                    self._dcell(P1W, rh, v1 if v1 is not None else '-', size=8.5)
                    self._dcell(P2W, rh, v2 if v2 is not None else '-', size=8.5)
                    if g and g.numeric_value is not None:
                        self._dcell(PMW, rh, g.numeric_value, bg=PROM_BG,
                                    bold=True, size=9)
                    else:
                        self._dcell(PMW, rh, '-', bg=PROM_BG, size=8.5)

            # Dibujar la celda de área fusionada (encima de los cursos) solo en áreas multi-curso
            if not single:
                self._draw_area_cell_direct(area_display, y_area, area_height)

            # Promedio final del área (num + letra) fusionado verticalmente
            x_pf = ML + AW + CW + len(terms) * BW
            nivel_st = student.nivel if getattr(student, 'nivel', None) else 'SECUNDARIA'
            vals = [d.get('promedio_num') for _, d in items
                    if d.get('promedio_num') is not None]
            if vals:
                avg = _round_half_up(sum(vals) / len(vals))
                qual = numeric_to_qualitative(avg, nivel_st)
            else:
                avg, qual = None, '--'
            self._draw_area_final(x_pf, y_area, area_height, avg, qual)

            # Mover Y al final del grupo
            self.set_y(y_area + area_height)

            # Línea gruesa de separación entre áreas
            y_sep = self.get_y()
            self._dc(BLACK)
            self.set_line_width(0.5)
            self.line(ML, y_sep, ML + PW, y_sep)
            self.set_line_width(0.2)

        self.ln(1.5)

    # =====================================================================
    # ESCALA DE VALORES + ASISTENCIA + SELLO
    # =====================================================================
    def _scale_attendance(self, ctx):
        meses   = ctx['meses']
        att_map = ctx['att_by_month']
        tf      = ctx['total_faltas']
        tt      = ctx['total_tardanzas']
        prom_a  = ctx['promedio_anual']

        sw = 60     # ancho bloque escala
        aw = PW - sw   # asistencia + situación final (debajo de TARDANZAS)

        lbl_w  = 20
        tot_w  = 12
        mw     = round((aw - lbl_w - tot_w) / len(meses), 2)

        y0 = self.get_y()

        # ── Escala ───────────────────────────────────────────────────────
        self._hcell(sw, 4.5, 'ESCALA DE VALORES', nx='LMARGIN', ny='NEXT')
        scale_rows = [
            ('DE 18 A 20', 'LOGRO DESTACADO',  'AD'),
            ('DE 14 A 17', 'LOGRO PROGRESIVO', 'A'),
            ('DE 11 A 13', 'EN PROCESO',        'B'),
            ('DE 00 A 10', 'EN INICIO',          'C'),
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

        # ── Asistencia ───────────────────────────────────────────────────
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
                self._dcell(mw, RH, f'{val:02d}' if val else '-', size=8.5)
            self._dcell(tot_w, RH, f'{total:02d}' if total else '-', bg=AREA_BG,
                        bold=True, size=8.5, nx='LMARGIN', ny='NEXT')

        # ── Situación final: debajo de TARDANZAS, ancho bloque asistencia ──
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

        # Avanzar Y al máximo entre escala (4 filas) y asistencia + sello
        scale_h = 4.5 + RH * 4
        att_h   = 4.5 + RH * 2 + 0.6 + h_box
        self.set_y(y0 + max(scale_h, att_h) + 2)
        self.ln(1)

    # =====================================================================
    # CONDUCTA + PPFF (una sola fila, dos columnas)
    # =====================================================================
    def _behavior_ppff_row(self, ctx):
        GAP = 2.0
        w_half = (PW - GAP) / 2.0
        xL = ML
        xR = ML + w_half + GAP
        rh = 3.8
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
            self._safe(
                'EVALUACIÓN DEL COMPORTAMIENTO DEL ALUMNO(A) DENTRO DE LA I.E.'),
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
            self._safe('EVALUACIÓN DE RESPONSABILIDAD DEL PPFF\nO APODERADO'),
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
        fs, fsh = 6.0, 6.5
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
        for mes in meses:
            month_beh = behavior_bm.get(mes, {})
            vals = [b.calificacion for b in month_beh.values()
                    if b and b.calificacion is not None]
            if vals:
                avg = round(sum(vals) / len(vals))
                self._dcell(mes_w, rh, str(avg), bg=PROM_BG, bold=True, size=fs)
            else:
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
        # Misma tipografía que las barras de título (Helvetica B 5.5, multi_cell h=2.35)
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

    # =====================================================================
    # COMENTARIOS DEL TUTOR
    # =====================================================================
    def _comments(self, ctx):
        terms    = ctx['terms']
        comments = ctx['comments_per_term']
        if not terms:
            return

        bim_names = ['I BIMESTRE', 'II BIMESTRE', 'III BIMESTRE', 'IV BIMESTRE']
        lw = 42

        self._section_bar(
            'RECOMENDACIONES DE PARTE DEL TUTOR(A) EN CADA BIMESTRE')

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

    # =====================================================================
    # FIRMAS
    # =====================================================================
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
        self.ln(4)
        self.set_x(ML)
        self._sig_line(sw, coord, line)
        self._sig_line(sw, (fb.get("director") or "").strip() or DEFAULT_DIRECTOR_GENERAL, line)
        self._sig_line(sw, tutor, line)
        self.set_x(ML); self.set_y(self.get_y() + 4)

        self.set_font('Helvetica', 'B', 7.5)
        self._tc(BRAND)
        for role in ("COORDINADOR(A)", "DIRECTOR GENERAL", "TUTOR DE AULA"):
            self.cell(sw, 4, role, align='C', new_x='RIGHT', new_y='LAST')
        self._reset()
        self.set_x(ML); self.set_y(self.get_y() + 4)

    # =====================================================================
    # FOOTER
    # =====================================================================
    # =====================================================================
    # ENTRY POINT
    # =====================================================================
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
def generate_boleta_secundaria_pdf(ctx: dict) -> bytes:
    return BoletaSecundariaPDF().build(ctx)


def generate_bulk_boletas_secundaria_pdf(ctx_list: list) -> bytes:
    return BoletaSecundariaPDF().build_bulk(ctx_list)

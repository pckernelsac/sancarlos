"""
Generador de PDF para el Cuadro de Mérito usando fpdf2.
Genera un PDF con logo, encabezado institucional y tabla de ranking.
"""
import os
from io import BytesIO
from fpdf import FPDF

# ── Paleta de colores ──────────────────────────────────────────────────────────
BRAND      = (14,  47, 119)   # #0e2f77
GOLD       = (234, 179, 8)    # dorado 1er puesto
SILVER     = (156, 163, 175)  # plata 2do puesto
BRONZE     = (217, 119, 6)    # bronce 3er puesto
AREA_BG    = (214, 228, 240)  # #d6e4f0
PROM_BG    = (220, 230, 241)  # #dce6f1
WHITE      = (255, 255, 255)
BLACK      = (0,   0,   0)
GRAY       = (130, 130, 130)
ROW_ALT    = (245, 247, 250)

BADGE = {
    'AD': {'bg': (219, 234, 254), 'fg': (30,  64, 175)},
    'A':  {'bg': (220, 252, 231), 'fg': (22, 101,  52)},
    'B':  {'bg': (254, 249, 195), 'fg': (113, 63,  18)},
    'C':  {'bg': (254, 226, 226), 'fg': (153, 27,  27)},
}

ML = 10
PW = 190


class RankingPDF(FPDF):

    def __init__(self):
        super().__init__('P', 'mm', 'A4')
        self.set_auto_page_break(auto=True, margin=15)

    @staticmethod
    def _safe(text):
        return text.encode('latin-1', errors='replace').decode('latin-1')

    def _fc(self, c): self.set_fill_color(*c)
    def _tc(self, c): self.set_text_color(*c)
    def _dc(self, c): self.set_draw_color(*c)
    def _reset(self): self._fc(WHITE); self._tc(BLACK); self._dc(BLACK)

    # ── Encabezado institucional ──────────────────────────────────────────────
    def _header_block(self, titulo_ranking, nivel, grado, anio):
        self.set_font('Helvetica', 'I', 6.5)
        self._tc(GRAY)
        self.cell(PW, 4,
                  self._safe('"Ano de la Esperanza y el Fortalecimiento de la Democracia"'),
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self._reset()

        y0 = self.get_y()

        # Logo
        logo_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'logosancarlos.png')
        if os.path.exists(logo_path):
            self.image(logo_path, ML, y0, 22, 22)
        else:
            self._dc(BRAND)
            self.rect(ML, y0, 22, 22)

        tx = ML + 24
        self.set_xy(tx, y0 + 0.5)
        self.set_font('Helvetica', 'B', 13)
        self._tc(BRAND)
        self.cell(145, 6, self._safe('INSTITUCION EDUCATIVA'),
                  align='C', new_x='LMARGIN', new_y='NEXT')

        self.set_x(tx)
        self.set_font('Helvetica', 'BI', 16)
        self.cell(145, 7, '"San Carlos"',
                  align='C', new_x='LMARGIN', new_y='NEXT')

        self.set_x(tx)
        self.set_font('Helvetica', 'I', 7.5)
        self._tc(GRAY)
        self.cell(145, 4, self._safe('"Nuestra Mision, ... Tu Exito...!"'),
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self._reset()

        # Contacto derecha
        lines = ['Av. San Carlos 406', 'Huancayo', 'Telf: 064-233700', 'Cel. 972648005']
        self.set_font('Helvetica', '', 5.5)
        self._tc(GRAY)
        for i, line in enumerate(lines):
            self.set_xy(ML + 168, y0 + 1 + i * 4)
            self.cell(22, 4, line, align='R', new_x='LMARGIN', new_y='NEXT')
        self._reset()

        self.set_y(y0 + 24)

        # Línea divisoria
        self._dc(BRAND)
        self.set_line_width(0.6)
        self.line(ML, self.get_y(), ML + PW, self.get_y())
        self.set_line_width(0.2)
        self.ln(3)

        # Título del ranking
        self.set_font('Helvetica', 'B', 14)
        self._tc(BRAND)
        self.cell(PW, 8, self._safe('CUADRO DE MERITO'), align='C',
                  new_x='LMARGIN', new_y='NEXT')

        grado_map = {
            '1': 'PRIMERO', '2': 'SEGUNDO', '3': 'TERCERO',
            '4': 'CUARTO', '5': 'QUINTO', '6': 'SEXTO',
        }
        grado_txt = grado_map.get(str(grado), str(grado))

        self.set_font('Helvetica', 'B', 11)
        self._tc(GRAY)
        self.cell(PW, 6,
                  self._safe(f'{titulo_ranking} - {grado_txt} DE {nivel} - {anio}'),
                  align='C', new_x='LMARGIN', new_y='NEXT')
        self._reset()
        self.ln(3)

    # ── Tabla de ranking ──────────────────────────────────────────────────────
    def _ranking_table(self, students):
        if not students:
            self.set_font('Helvetica', 'I', 10)
            self._tc(GRAY)
            self.cell(PW, 10, 'No hay notas registradas.', align='C',
                      new_x='LMARGIN', new_y='NEXT')
            self._reset()
            return

        # Anchos de columna
        rank_w = 20
        name_w = 100
        sec_w  = 20
        prom_w = 25
        nivel_w = PW - rank_w - name_w - sec_w - prom_w

        rh = 8

        # Header
        self.set_font('Helvetica', 'B', 8)
        self._fc(BRAND); self._tc(WHITE)
        self.cell(rank_w, rh, 'PUESTO', border=1, align='C', fill=True)
        self.cell(name_w, rh, 'ESTUDIANTE', border=1, align='C', fill=True)
        self.cell(sec_w, rh, self._safe('SECCION'), border=1, align='C', fill=True)
        self.cell(prom_w, rh, 'PROMEDIO', border=1, align='C', fill=True)
        self.cell(nivel_w, rh, 'NIVEL', border=1, align='C', fill=True,
                  new_x='LMARGIN', new_y='NEXT')
        self._reset()

        # Filas
        for i, item in enumerate(students):
            # Fondo alternado
            bg = ROW_ALT if i % 2 == 1 else WHITE
            # Fondo especial para top 3
            if item['rank'] == 1:
                bg = (254, 252, 232)  # amarillo suave
            elif item['rank'] == 2:
                bg = (249, 250, 251)  # gris suave
            elif item['rank'] == 3:
                bg = (255, 247, 237)  # naranja suave

            self._fc(bg)

            # Puesto
            self.set_font('Helvetica', 'B', 10)
            rank_text = str(item['rank'])
            if item['rank'] <= 3:
                self._tc(BRAND)
            else:
                self._tc(BLACK)
            self.cell(rank_w, rh, self._safe(f'{rank_text}'), border=1,
                      align='C', fill=True)

            # Nombre
            self.set_font('Helvetica', '', 8)
            self._tc(BLACK)
            self.cell(name_w, rh, self._safe(f'  {item["student"].full_name}'),
                      border=1, align='L', fill=True)

            # Sección
            self.set_font('Helvetica', '', 8)
            self._tc(GRAY)
            self.cell(sec_w, rh, item['student'].seccion, border=1,
                      align='C', fill=True)

            # Promedio
            self.set_font('Helvetica', 'B', 10)
            self._tc(BRAND)
            self.cell(prom_w, rh, str(item['promedio']), border=1,
                      align='C', fill=True)

            # Badge nivel cualitativo
            cual = item.get('cual', '--')
            badge = BADGE.get(cual)
            if badge:
                self._fc(badge['bg']); self._tc(badge['fg'])
            else:
                self._fc(bg); self._tc(BLACK)
            self.set_font('Helvetica', 'B', 9)
            self.cell(nivel_w, rh, cual, border=1, align='C', fill=True,
                      new_x='LMARGIN', new_y='NEXT')
            self._reset()

    # ── Pie de página ─────────────────────────────────────────────────────────
    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 6.5)
        self._tc(GRAY)
        self.cell(0, 4, self._safe('I.E. "San Carlos" - Huancayo'),
                  align='L')
        self.cell(0, 4, self._safe(f'Pagina {self.page_no()}/{{nb}}'),
                  align='R')


def generate_ranking_pdf(ranking_data, terms, nivel, grado, anio):
    """
    Genera un PDF con todos los cuadros de mérito (cada bimestre + anual).
    Retorna un BytesIO con el PDF.
    """
    pdf = RankingPDF()
    pdf.alias_nb_pages()

    # Una página por cada bimestre que tenga datos
    for term in terms:
        students = ranking_data.get(term.id, [])
        pdf.add_page()
        pdf._header_block(term.nombre.upper(), nivel, grado, anio)
        pdf._ranking_table(students)

    # Página anual
    students_anual = ranking_data.get("anual", [])
    pdf.add_page()
    pdf._header_block('PROMEDIO ANUAL', nivel, grado, anio)
    pdf._ranking_table(students_anual)

    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer

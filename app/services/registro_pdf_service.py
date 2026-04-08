"""
PDF del Registro Auxiliar (por curso / EDA / aula). Formato horizontal A4.
"""
from fpdf import FPDF

from app.services.registro_service import (
    CAMPOS_SEMANA,
    CAMPOS_SEMANA_3,
    DEFAULT_HEADERS,
    SEMANAS,
    escala_academica_text,
)

BRAND = (14, 47, 119)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (100, 100, 100)
HDR_BG = (214, 228, 240)
ROW_ALT = (248, 250, 252)


class RegistroAuxiliarPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.set_auto_page_break(auto=False)
        self.set_margins(8, 8, 8)

    @staticmethod
    def _safe(text) -> str:
        if text is None:
            return ""
        return str(text).encode("latin-1", errors="replace").decode("latin-1")

    def _fc(self, c):
        self.set_fill_color(*c)

    def _tc(self, c):
        self.set_text_color(*c)

    def _dc(self, c):
        self.set_draw_color(*c)

    def _reset(self):
        self._fc(WHITE)
        self._tc(BLACK)
        self._dc(BLACK)

    def footer(self):
        self.set_y(-10)
        self.set_font("Helvetica", "I", 6)
        self._tc(GRAY)
        pw = self._pw()
        self.set_x(self.l_margin)
        self.cell(pw * 0.55, 4, self._safe('I.E. "San Carlos" - Huancayo'), align="L", ln=0)
        self.cell(pw * 0.45, 4, self._safe(f"Pág. {self.page_no()}/{{nb}}"), align="R", ln=1)
        self._reset()

    def _pw(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def _column_widths(self) -> list[float]:
        pw = self._pw()
        w_num = 5.0
        w_name = 42.0
        w_pre, w_ex, w_cu, w_ql, w_es = 7.0, 7.0, 8.0, 7.0, 34.0
        n_small = 22
        fixed = w_num + w_name + w_pre + w_ex + w_cu + w_ql + w_es
        w_s = (pw - fixed) / n_small
        cols = [w_num, w_name] + [w_s] * n_small
        cols.extend([w_pre, w_ex, w_cu, w_ql, w_es])
        return cols

    def _hdr_txt(self, field: str, headers: dict) -> str:
        s = headers.get(field) or DEFAULT_HEADERS.get(field, field)
        s = self._safe(s).replace("\n", " ")
        return (s[:7] + ".") if len(s) > 8 else s

    def _draw_title(self, data: dict, grado: str, seccion: str):
        eda = data.get("eda")
        course = data.get("course")
        term = data.get("term")
        self.set_font("Helvetica", "B", 12)
        self._tc(BRAND)
        self.cell(self._pw(), 6, self._safe("REGISTRO AUXILIAR"), align="C", ln=1)
        self.set_font("Helvetica", "B", 9)
        self._tc(BLACK)
        line = (
            f"{course.nombre} ({course.area})  |  {eda.nombre}  |  "
            f"{term.nombre} {term.anio}  |  {course.nivel} {grado}° sección {seccion}"
        )
        self.cell(self._pw(), 5, self._safe(line), align="C", ln=1)
        self.ln(2)

    def _draw_header_rows(self, headers: dict, cw: list[float], h: float = 5.0):
        """Una fila de cabecera con abreviaturas (A4 horizontal)."""
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 4.6)
        self._fc(HDR_BG)
        self._tc(BLACK)
        self.cell(cw[0], h, "N°", border=1, align="C", fill=True, ln=0)
        self.cell(cw[1], h, self._safe("Apellidos y nombres"), border=1, align="C", fill=True, ln=0)
        idx = 2
        for sem in SEMANAS:
            campos = CAMPOS_SEMANA_3 if sem == 3 else CAMPOS_SEMANA
            for f in campos:
                lab = f"S{sem}" + self._hdr_txt(f, headers)[:5]
                self.cell(cw[idx], h, self._safe(lab), border=1, align="C", fill=True, ln=0)
                idx += 1
            self.cell(cw[idx], h, f"S{sem}P", border=1, align="C", fill=True, ln=0)
            idx += 1
        tail = list(zip(["PrePr", "Examen", "P.cnt", "P.cual", "Escala"], cw[-5:]))
        for j, (lab, w) in enumerate(tail):
            ln = 1 if j == len(tail) - 1 else 0
            self.cell(w, h, self._safe(lab), border=1, align="C", fill=True, ln=ln)
        self._reset()

    def _maybe_new_page(self, cw: list[float], headers: dict, row_h: float, y_max: float = 188):
        if self.get_y() + row_h > y_max:
            self.add_page()
            self._draw_header_rows(headers, cw, h=5.0)

    def _draw_student_row(
        self,
        data: dict,
        headers: dict,
        cw: list[float],
        row_h: float,
        idx: int,
        student,
        fill_alt: bool,
    ):
        semana_map = data.get("semana_map") or {}
        weekly_prom = data.get("weekly_prom") or {}
        pre_prom = data.get("pre_prom") or {}
        examen_map = data.get("examen_map") or {}
        cuant_map = data.get("cuant_map") or {}
        cual_map = data.get("cual_map") or {}
        course = data.get("course")
        nivel = course.nivel if course else "PRIMARIA"

        self._maybe_new_page(cw, headers, row_h)
        bg = ROW_ALT if fill_alt else WHITE
        self.set_font("Helvetica", "", 5.2)
        x0 = self.l_margin
        self.set_x(x0)
        self._fc(bg)
        self._tc(BLACK)
        self.cell(cw[0], row_h, str(idx), border=1, align="C", fill=True, ln=0)
        name = student.full_name
        if len(name) > 34:
            name = name[:32] + "…"
        self.cell(cw[1], row_h, self._safe(name), border=1, align="L", fill=True, ln=0)

        col_i = 2
        for sem in SEMANAS:
            campos = CAMPOS_SEMANA_3 if sem == 3 else CAMPOS_SEMANA
            r = semana_map.get((student.id, sem))
            for f in campos:
                v = getattr(r, f, None) if r else None
                txt = "" if v is None else str(v)
                self.cell(cw[col_i], row_h, txt, border=1, align="C", fill=True, ln=0)
                col_i += 1
            ps = weekly_prom.get((student.id, sem))
            self.cell(
                cw[col_i],
                row_h,
                "" if ps is None else str(ps),
                border=1,
                align="C",
                fill=True,
                ln=0,
            )
            col_i += 1

        pp = pre_prom.get(student.id)
        self.cell(cw[col_i], row_h, "" if pp is None else str(pp), border=1, align="C", fill=True, ln=0)
        col_i += 1
        ex = examen_map.get(student.id)
        self.cell(cw[col_i], row_h, "" if ex is None else str(ex), border=1, align="C", fill=True, ln=0)
        col_i += 1
        cq = cuant_map.get(student.id)
        self.cell(cw[col_i], row_h, "" if cq is None else str(cq), border=1, align="C", fill=True, ln=0)
        col_i += 1
        ql = cual_map.get(student.id, "") or ""
        if ql == "--":
            ql = ""
        self.cell(cw[col_i], row_h, self._safe(ql), border=1, align="C", fill=True, ln=0)
        col_i += 1
        esc = escala_academica_text(cq, nivel)
        self.set_font("Helvetica", "", 4.5)
        self.cell(cw[col_i], row_h, self._safe(esc[:22]), border=1, align="C", fill=True, ln=1)
        self._reset()

    def build(self, data: dict, headers: dict, grado: str, seccion: str):
        self.alias_nb_pages()
        self.add_page()
        self._draw_title(data, grado, seccion)
        cw = self._column_widths()
        self._draw_header_rows(headers, cw, h=5.0)

        students = data.get("students") or []
        row_h = 4.0
        for i, s in enumerate(students, start=1):
            self._draw_student_row(
                data, headers, cw, row_h, i, s, fill_alt=(i % 2 == 0),
            )

        if not students:
            self.set_font("Helvetica", "I", 8)
            self._tc(GRAY)
            self.cell(self._pw(), 8, self._safe("No hay estudiantes en esta aula."), align="C", ln=1)
            self._reset()


def generate_registro_auxiliar_pdf_bytes(data: dict, headers: dict, *, grado: str, seccion: str) -> bytes:
    pdf = RegistroAuxiliarPDF()
    pdf.build(data, headers, grado, seccion)
    raw = pdf.output(dest="S")
    if isinstance(raw, str):
        return raw.encode("latin-1")
    return bytes(raw)

from typing import Literal, Optional
from pydantic import BaseModel, Field


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class Item(BaseModel):
    """Tüm öğelerin ortak alanları."""
    id: str                      # table_1, eq_1, fig_1
    sira: int                    # makaledeki okuma sırası
    page: int                    # sayfa numarası (1'den başlar)
    bbox: Optional[BBox] = None  # sayfadaki konum
    status: Literal["ok", "failed", "skipped"] = "ok"
    warning: Optional[str] = None  # düşük güvenilirlik notu
    error: Optional[str] = None    # failed ise hata mesajı


class TableItem(Item):
    caption: Optional[str] = None
    markdown: str = ""


class FigureItem(Item):
    caption: Optional[str] = None
    description: str = ""


class EquationItem(Item):
    latex: str = ""


class PaperResult(BaseModel):
    paper_id: str
    docling_device: str = ""
    tables: list[TableItem] = Field(default_factory=list)
    figures: list[FigureItem] = Field(default_factory=list)
    equations: list[EquationItem] = Field(default_factory=list)
    model: str = ""
    sure_sn: float = 0.0
    messages: list[str] = Field(default_factory=list)
    okuma_sirasi: list[str] = Field(default_factory=list)


if __name__ == "__main__":
    ornek = PaperResult(
        paper_id="ornek",
        model="gemini-3.8-flash",
        sure_sn=12.5,
        tables=[TableItem(
            id="table_1", sira=2, page=3,
            bbox=BBox(x0=50, y0=100, x1=300, y1=220),
            caption="Model karşılaştırması",
            markdown="| Model | F1 |\n|---|---|\n| BERT | 89.5 |",
        )],
        equations=[EquationItem(
            id="eq_1", sira=1, page=2,
            latex=r"L = -\sum_{i} y_i \log \hat{y}_i",
        )],
        messages=["Bu makalede figür bulunamadı"],
    )
    print(ornek.model_dump_json(indent=2))
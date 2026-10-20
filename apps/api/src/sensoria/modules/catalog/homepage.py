"""Validated, explicitly public homepage copy stored in ``app_settings``."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

HOMEPAGE_SETTING_KEY = "homepage.content.v1"


class HomepageHeadline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    before_emphasis: str = Field(min_length=1, max_length=120)
    emphasis: str = Field(min_length=1, max_length=120)
    after_emphasis: str = Field(min_length=1, max_length=120)


class HomepageBenefit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    icon: Literal["payment", "email", "parcel", "voucher"]
    text: str = Field(min_length=1, max_length=180)


class HomepageProductSelection(BaseModel):
    """Optional editorial product IDs; absent/stale IDs use a public fallback."""

    model_config = ConfigDict(extra="forbid")

    voucher_id: UUID | None = None
    audiobook_id: UUID | None = None
    course_id: UUID | None = None


class HomepageContent(BaseModel):
    """Whitelisted public copy; never returns arbitrary settings or secrets."""

    model_config = ConfigDict(extra="forbid")

    eyebrow: str = Field(min_length=1, max_length=160)
    headline: HomepageHeadline
    paragraph: str = Field(min_length=1, max_length=600)
    catalog_button_label: str = Field(min_length=1, max_length=80)
    voucher_button_label: str = Field(min_length=1, max_length=80)
    catalog_button_target: Literal["/sklep"] = "/sklep"
    benefits: list[HomepageBenefit] = Field(min_length=4, max_length=4)
    product_selection: HomepageProductSelection = Field(default_factory=HomepageProductSelection)

    @model_validator(mode="after")
    def validate_benefit_keys(self) -> "HomepageContent":
        """Keep the four presentation icons unique for stable accessible rendering."""

        keys = [benefit.icon for benefit in self.benefits]
        if set(keys) != {"payment", "email", "parcel", "voucher"}:
            raise ValueError("homepage benefits must contain each known icon once")
        return self


DEFAULT_HOMEPAGE_CONTENT = HomepageContent(
    eyebrow="INSTYTUT DIAGNOZY I TERAPII SENSORIA",
    headline=HomepageHeadline(
        before_emphasis="Terapia",
        emphasis="nie kończy się",
        after_emphasis="w gabinecie.",
    ),
    paragraph=(
        "Vouchery na wizyty, książki, audiobooki i kursy przygotowane przez zespół, "
        "który od ponad dwudziestu lat pracuje z dziećmi, młodzieżą i dorosłymi."
    ),
    catalog_button_label="Zobacz materiały",
    voucher_button_label="Kup voucher na wizytę",
    benefits=[
        HomepageBenefit(icon="payment", text="Płatność w 15 sekund"),
        HomepageBenefit(icon="email", text="Pliki od razu na mailu"),
        HomepageBenefit(icon="parcel", text="Paczkomat 24/7"),
        HomepageBenefit(icon="voucher", text="Voucher ważny 12 miesięcy"),
    ],
)

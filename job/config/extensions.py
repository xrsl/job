"""Extended model classes with helper methods.

These classes extend the auto-generated models with additional functionality.
This allows models.py to remain purely auto-generated.
"""

from pydantic import Field

from . import models


class CareerPage(models.CareerPage):
    """Extended CareerPage with defaults and helper methods."""

    # Override with better defaults
    enabled: bool = True
    extra_keywords: list[str] = Field(default_factory=list, alias="extra-keywords")
    keywords: list[str] = Field(default_factory=list)

    model_config = models.CareerPage.model_config | {"populate_by_name": True}

    def __str__(self) -> str:
        return f"{self.company} ({self.url})"


class JobSearch(models.JobSearch):
    """Extended JobSearch with helper methods and properties."""

    # Override with better defaults
    in_: list[CareerPage] = Field(default_factory=list, alias="in")
    keywords: list[str] = Field(default_factory=list)

    model_config = models.JobSearch.model_config | {"populate_by_name": True}

    @property
    def pages(self) -> list[CareerPage]:
        """Alias for in_ for better readability."""
        return self.in_

    @pages.setter
    def pages(self, value: list[CareerPage]) -> None:
        """Setter for pages property."""
        self.in_ = value

    @property
    def enabled_pages(self) -> list[CareerPage]:
        """Return only enabled pages."""
        return [p for p in self.in_ if p.enabled]

    def get_keywords_for_page(self, page: CareerPage) -> list[str]:
        """Get keywords for a page.

        If page has custom keywords, use those.
        Otherwise, use defaults + any extra_keywords.
        """
        if page.keywords:
            return page.keywords
        # Merge defaults with extra keywords (deduplicated, preserving order)
        combined = list(self.keywords)
        for kw in page.extra_keywords:
            if kw not in combined:
                combined.append(kw)
        return combined


class JobAdd(models.JobAdd):
    """Extended JobAdd with better defaults."""

    browser: bool = False
    structured: bool = False

    model_config = models.JobAdd.model_config | {"populate_by_name": True}


class JobExport(models.JobExport):
    """Extended JobExport with better defaults."""

    output_format: str = Field(default="json", alias="output-format")

    model_config = models.JobExport.model_config | {"populate_by_name": True}


class JobFit(models.JobFit):
    """Extended JobFit with better defaults."""

    extra: list[str] = Field(default_factory=list)

    model_config = models.JobFit.model_config | {"populate_by_name": True}


class JobGH(models.JobGH):
    """Extended JobGH with better defaults."""

    auto_assign: bool = Field(default=False, alias="auto-assign")
    default_labels: list[str] = Field(default_factory=list, alias="default-labels")

    model_config = models.JobGH.model_config | {"populate_by_name": True}


class JobSettings(models.JobSettings):
    """Extended JobSettings with better defaults."""

    add: JobAdd = Field(default_factory=JobAdd)
    export: JobExport = Field(default_factory=JobExport)
    fit: JobFit = Field(default_factory=JobFit)
    gh: JobGH = Field(default_factory=JobGH)
    search: JobSearch = Field(default_factory=JobSearch)
    verbose: bool = False

    model_config = models.JobSettings.model_config | {"populate_by_name": True}

from dataclasses import dataclass, field
from typing import List


@dataclass
class ResourceItem:
    title: str
    url: str
    file_size_str: str
    file_size_bytes: int
    resource_type: str
    section_name: str


@dataclass
class Section:
    name: str
    items: List[ResourceItem] = field(default_factory=list)

    @property
    def total_size_bytes(self) -> int:
        return sum(i.file_size_bytes for i in self.items)


@dataclass
class CourseData:
    title: str
    url: str
    folder_name: str
    sections: List[Section] = field(default_factory=list)

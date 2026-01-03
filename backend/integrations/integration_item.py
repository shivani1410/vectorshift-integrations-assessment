from datetime import datetime
from typing import Optional, List


class IntegrationItem:
    def __init__(
        self,
        id: Optional[str] = None,
        type: Optional[str] = None,
        directory: bool = False,
        parent_path_or_name: Optional[str] = None,
        parent_id: Optional[str] = None,
        name: Optional[str] = None,
        creation_time: Optional[datetime] = None,
        last_modified_time: Optional[datetime] = None,
        url: Optional[str] = None,
        children: Optional[List[str]] = None,
        mime_type: Optional[str] = None,
        delta: Optional[str] = None,
        drive_id: Optional[str] = None,
        visibility: Optional[bool] = True,
    ):
        self.id = id
        self.type = type
        self.directory = directory
        self.parent_path_or_name = parent_path_or_name
        self.parent_id = parent_id
        self.name = name
        self.creation_time = creation_time
        self.last_modified_time = last_modified_time
        self.url = url
        self.children = children
        self.mime_type = mime_type
        self.delta = delta
        self.drive_id = drive_id
        self.visibility = visibility

    def __repr__(self):
        return f"IntegrationItem(id={self.id}, type={self.type}, name={self.name}, parent_id={self.parent_id}, parent_path_or_name={self.parent_path_or_name}, creation_time={self.creation_time}, last_modified_time={self.last_modified_time})"

    def __str__(self):
        return f"{self.id} {self.type} {self.name} {self.parent_id} {self.parent_path_or_name} {self.creation_time} {self.last_modified_time}"

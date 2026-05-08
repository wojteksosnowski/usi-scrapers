from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    @staticmethod
    @abstractmethod
    def transform(raw_data: dict, investment_slug: str, developer_slug: str) -> dict:
        """
        Transforms raw vendor-specific JSON into the unified USI schema.
        """
        pass

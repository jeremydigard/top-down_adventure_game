from abc import ABC, abstractmethod

class WeaponHittable(ABC):
    @abstractmethod
    def on_weapon_hit(self) -> None:
        ...

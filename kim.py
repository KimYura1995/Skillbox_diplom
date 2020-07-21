# -*- coding: utf-8 -*-

from astrobox.core import Drone
from robogame_engine.geometry import Point
from robogame_engine.theme import theme

import math


class KimDrone(Drone):
    my_team = list()
    asteroids_info = dict()
    total_distance_empty = 0
    total_distance_full = 0
    total_distance_half_empty = 0
    max_drone_capacity = 100
    first_target = list()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.target = None
        self.next_target = None
        self.half_way_target = None

    def _get_first_asteroid(self):
        """Генерация очереди первом пуске"""
        if not any(KimDrone.first_target):
            KimDrone.first_target = sorted(self.asteroids, key=lambda x: self.distance_to(x), reverse=True)
        return KimDrone.first_target.pop()

    def _update_info_asteroids(self):
        """Обновление информацию об астероидах (очередь)"""
        if any(KimDrone.asteroids_info):
            for asteroid in self.asteroids:
                aster_info = KimDrone.asteroids_info[asteroid.id]
                aster_info["future_payload"] = asteroid.payload
                aster_info["max_queue"] = math.ceil(asteroid.payload / KimDrone.max_drone_capacity)
        else:
            for asteroid in self.asteroids:
                KimDrone.asteroids_info[asteroid.id] = dict(
                    current_queue=set(),
                    max_queue=math.ceil(asteroid.payload / KimDrone.max_drone_capacity),
                    future_payload=asteroid.payload
                )

    def _get_my_asteroid(self, payload_trigger=False):
        """Получение ближайшего астероида с ресурсом"""
        if payload_trigger is True:
            sort_asteroids = sorted(self.asteroids, key=lambda x: x.payload, reverse=True)
        else:
            sort_asteroids = sorted(self.asteroids, key=lambda x: self.distance_to(x))
        for asteroid in sort_asteroids:
            aster_info = KimDrone.asteroids_info[asteroid.id]
            if (len(aster_info["current_queue"]) < aster_info["max_queue"]) and (aster_info["future_payload"] > 0):
                aster_info["future_payload"] -= KimDrone.max_drone_capacity - self.payload
                return asteroid

    def _append_queue(self):
        """Добавление в очередь на астероид"""
        aster_info = KimDrone.asteroids_info[self.target.id]
        if len(aster_info["current_queue"]) < aster_info["max_queue"]:
            KimDrone.asteroids_info[self.target.id]["current_queue"].add(self.id)
        else:
            self.target = None

    def _delete_queue(self):
        """Удвление из очереди на астероид"""
        for asteroid in self.asteroids:
            if self.id in KimDrone.asteroids_info[asteroid.id]["current_queue"]:
                KimDrone.asteroids_info[asteroid.id]["current_queue"].remove(self.id)

    def _half_way_target(self):
        """Расчет средней точки между дроном и целью"""
        x = int((self.coord.x + self.target.x)/2)
        y = int((self.coord.y + self.target.y)/2)
        self.half_way_target = Point(x, y)
        return self.half_way_target

    def on_born(self):
        """Рождение дрона"""
        self._update_info_asteroids()
        self.target = self._get_first_asteroid()
        self.move_at(self.target)
        self.my_team.append(self)

    def on_stop_at_target(self, target):
        """Остановка у цели"""
        if self.half_way_target and self.half_way_target == target:
            if not self.target.is_empty:
                self.move_at(self.target)
            else:
                # TODO - Для повышения читаемости кода, здесь нужно код ветки выделить в метод с красноречивым названием
                self.target = self._get_my_asteroid()
                if self.target:
                    self.move_at(self._half_way_target())
                else:
                    self.move_at(self.my_mothership)
        else:
            super(KimDrone, self).on_stop_at_target(target)

    def on_stop_at_asteroid(self, asteroid):
        """Остановка у астероида"""
        self._update_info_asteroids()
        self.next_target = self._get_my_asteroid()
        self.turn_to(self.my_mothership)
        self.load_from(asteroid)

    def on_load_complete(self):
        """Завершение загрузки"""
        self._update_info_asteroids()
        self._delete_queue()
        self.target = self._get_my_asteroid()
        if self.is_full or self.target is None:
            self.move_at(self.my_mothership)
        elif self.target:
            self.move_at(self._half_way_target())
        else:
            self.move_at(self.my_mothership)

    def on_stop_at_mothership(self, mothership):
        """Остановка у корабля-носителя"""
        self._update_info_asteroids()
        self.next_target = self._get_my_asteroid()
        if self.next_target:
            self.turn_to(self.next_target)
        self.unload_to(mothership)

    def on_unload_complete(self):
        """Выгрузка завершена"""
        self._update_info_asteroids()
        self.target = self._get_my_asteroid(payload_trigger=True)
        if self.target is None:
            self.stop()
        else:
            self._append_queue()
            self.move_at(self._half_way_target())
        self.print_stat()

    def move_at(self, target, speed=None):
        """Двигаться до цели"""
        super().move_at(target, speed)
        if self.is_full:
            KimDrone.total_distance_full += self.distance_to(target)
        elif self.is_empty:
            KimDrone.total_distance_empty += self.distance_to(target)
        else:
            KimDrone.total_distance_half_empty += self.distance_to(target)

    def on_wake_up(self):
        if self.health < theme.DRONE_MAX_SHIELD:
            self.move_at(self.my_mothership)

    def print_stat(self):
        if all(aster.is_empty for aster in self.asteroids) and all(drone.is_empty for drone in KimDrone.my_team):
            self.logger.warning(f"Пройдено расстояние полным:{int(KimDrone.total_distance_full)}, "
                                f"пустым:{int(KimDrone.total_distance_empty)}, "
                                f"полупустым:{int(KimDrone.total_distance_half_empty)}")



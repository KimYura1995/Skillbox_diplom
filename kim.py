# -*- coding: utf-8 -*-
import random
from abc import ABC, abstractmethod
from math import sqrt, degrees, acos
from astrobox.core import Drone
from robogame_engine.geometry import Vector, Point
from robogame_engine.theme import theme


# Константы
_MAX_PAYLOAD_RETURN_MOTHERSHIP = 90
_MIN_HEALTH_WHITE_FLAG = 0.8
_MAX_RADIUS_SEARCH = 580
_DISTANCE_TO_SHOT = 580
_MIN_ANGLE_ATTACK = 10


class DataObjects:
    """Данные об объектах карты"""

    def __init__(self):
        self._my_team = list()
        self._my_base = None

    @property
    def my_team(self):
        """Моя команда дронов"""
        return [drone for drone in self._my_team if drone.is_alive]

    @property
    def my_units(self):
        """Мои юниты (дроны, база)"""
        team = self._my_team.copy()
        team.append(self._my_base)
        return [drone for drone in team if drone.is_alive]

    def add_drone_in_my_team(self, drone):
        """Добавить дрон в мою команду"""
        self._my_team.append(drone)

    def get_enemy_drones(self, unit):
        """Получить всех вражеских дронов"""
        return [enemy for enemy in unit.scene.drones if enemy not in self._my_team]

    def get_enemy_motherships(self, unit):
        """Получить все вражеские базы"""
        return [base for base in unit.scene.motherships if base is not unit.my_mothership]

    def get_target_for_collecting_resource(self, unit):
        """Получить объекты с ресурсом для сбора"""
        list_target = list()
        asteroids = [asteroid for asteroid in unit.asteroids if not asteroid.is_empty]
        list_target.extend(asteroids)
        drones = [drone for drone in unit.scene.drones if drone.payload > 0 and (not drone.is_alive)]
        list_target.extend(drones)
        bases = [base for base in self.get_enemy_motherships(unit) if base.payload > 0 and (not base.is_alive)]
        list_target.extend(bases)
        return list_target


class State(ABC):
    """Состояние"""
    data = DataObjects()
    list_occupied_objects = list()

    def _adding_and_removing_queue(self, unit, target=None):
        """Добавить/удалить цель из очереди"""
        if unit.target in self.list_occupied_objects:
            self.list_occupied_objects.remove(unit.target)
        if target and target not in self.data.get_enemy_motherships(unit):
            self.list_occupied_objects.append(target)

    @abstractmethod
    def move_to_target(self, unit):
        pass

    @abstractmethod
    def action_on_target(self, unit):
        pass


class CollectorState(State):
    """Состояние Сборщик"""

    def get_target_for_harvest(self, unit, turn=False):
        """Получить цель для сбора"""
        list_target = sorted(self.data.get_target_for_collecting_resource(unit),
                             key=lambda x: unit.distance_to(x))
        for target in list_target:
            if target not in self.list_occupied_objects:
                if turn is False:
                    self._adding_and_removing_queue(target=target, unit=unit)
                return target

    def move_to_target(self, unit):
        """Движение к цели"""
        unit.target = self.get_target_for_harvest(unit)
        if unit.payload >= _MAX_PAYLOAD_RETURN_MOTHERSHIP or unit.target is None:
            unit.move_at(unit.my_mothership)
        else:
            unit.move_at(unit.target)

    def action_on_target(self, unit):
        """Действие у цели"""
        if unit.near(unit.my_mothership):
            target_turn = self.get_target_for_harvest(unit, turn=True)
            if target_turn:
                unit.turn_to(target_turn)
            if unit.is_empty:
                self.move_to_target(unit)
            else:
                unit.unload_to(unit.my_mothership)
        else:
            if unit.target and unit.near(unit.target):
                unit.load_from(unit.target)
                unit.target = self.get_target_for_harvest(unit)
            else:
                unit.target = self.get_target_for_harvest(unit)
                self.move_to_target(unit)


class WhiteFlagState(State):
    """Состояние 'Белый флаг' (Бросить всё и вернуться на базу)"""

    def move_to_target(self, unit):
        """Движение к цели"""
        self._adding_and_removing_queue(unit)
        unit.move_at(unit.my_mothership)

    def action_on_target(self, unit):
        """Действие у цели"""
        self._adding_and_removing_queue(unit)
        unit.move_at(unit.my_mothership)


class AttackingState(State):
    """Агрессивное состояние (атака цели)"""

    def normalize_vector(self, vector):
        """Нормализировать вектор"""
        len_vector = vector.module
        return Vector(vector.x / len_vector, vector.y / len_vector)

    def scalar_vector_multiplication(self, vector1, vector2):
        """Скалярное произведение вектора"""
        result = vector1.x * vector2.x + vector1.y * vector2.y
        return result

    def checking_the_line_of_fire(self, unit, target, point=None):
        """Проверить, что на линии огня нет союзников"""
        if point is None:
            point = unit.coord
        vec_target_self = Vector(target.coord.x - point.x, target.coord.y - point.y)
        norm_vec_target_self = self.normalize_vector(vec_target_self)
        for friendly in self.data.my_units:
            if friendly is not unit:
                if friendly.distance_to(point) <= friendly.radius * 1.5:
                    return False
                vec_target_friendly = Vector(target.coord.x - friendly.coord.x, target.coord.y - friendly.coord.y)
                norm_vec_target_friendly = self.normalize_vector(vec_target_friendly)
                scalar = self.scalar_vector_multiplication(norm_vec_target_self, norm_vec_target_friendly)
                try:
                    angle = degrees(acos(scalar))
                except:
                    return False
                if angle < _MIN_ANGLE_ATTACK \
                        and (friendly.distance_to(target) < point.distance_to(target)):
                    return False
        else:
            return True

    def search_new_place_for_attack(self, unit):
        """Поиск нового места для атаки цели"""
        enemy = unit.target_for_attack
        vector_target_self = Vector(unit.coord.x - enemy.coord.x, unit.coord.y - enemy.coord.y)
        norm_vector = self.normalize_vector(vector_target_self)
        for dist in range(max(int(unit.distance_to(enemy)), _DISTANCE_TO_SHOT), 200, -50):
            for angle in range(100):
                vector_gun_range = norm_vector * dist
                dice = random.randint(-5, 6)
                vector_gun_range.rotate(dice * 5)
                point_to_attack = Point(enemy.x + vector_gun_range.x, enemy.y + vector_gun_range.y)
                if self.checking_the_line_of_fire(unit=unit, point=point_to_attack, target=unit.target_for_attack)\
                        and (unit.radius < point_to_attack.x < theme.FIELD_WIDTH)\
                        and (unit.radius < point_to_attack.y < theme.FIELD_HEIGHT):
                    return point_to_attack

    def attacking(self, unit):
        """Атака или перемещение к цели"""
        if self.checking_the_line_of_fire(unit=unit, target=unit.target_for_attack):
            unit.turn_to(unit.target_for_attack)
            unit.gun.shot(unit.target_for_attack)
        else:
            point = self.search_new_place_for_attack(unit)
            if point:
                unit.move_at(point)
            else:
                unit.all_target_empty()

    def move_to_target(self, unit):
        """Движение к цели"""
        self.attacking(unit)

    def action_on_target(self, unit):
        """Действие у цели"""
        self.attacking(unit)


class KimDrone(Drone):
    """Дрон"""

    def __init__(self):
        super().__init__()
        self.target = None
        self.target_for_attack = None
        self._state = CollectorState()

    def change_state(self):
        """Смена состояния"""
        if self.meter_2 <= _MIN_HEALTH_WHITE_FLAG:
            self._state = WhiteFlagState()
            self.target_for_attack = None
        elif self.is_empty and self.search_for_enemies_in_radius():
            self._state = AttackingState()
        elif self.is_empty and self.all_target_empty():
            self._state = AttackingState()
        else:
            self._state = CollectorState()
            self.target_for_attack = None

    def on_born(self):
        """Рождение дрона"""
        self._state.data.add_drone_in_my_team(self)
        self._state.data._my_base = self.my_mothership
        self._state.move_to_target(self)

    def on_stop_at_target(self, target):
        """Остановка у цели"""
        self._state.action_on_target(self)
        self.change_state()

    def on_load_complete(self):
        """Загрузка завершена"""
        self._state.move_to_target(self)
        self.change_state()

    def on_unload_complete(self):
        """Разгрузка завершена"""
        self._state.move_to_target(self)
        self.change_state()

    def on_wake_up(self):
        """Проснуться"""
        self._state.action_on_target(self)
        self.change_state()

    def search_for_enemies_in_radius(self):
        """Находится, ли вражеский дрон в радиусе поиска"""
        for enemy in sorted(self._state.data.get_enemy_drones(self), key=lambda x: x.distance_to(self)):
            if (sqrt((enemy.coord.x - self.coord.x) ** 2 + (enemy.coord.y - self.coord.y) ** 2) <= _MAX_RADIUS_SEARCH) \
                    and enemy.is_alive:
                self.target_for_attack = enemy
                return True

    def all_target_empty(self):
        """Если нет целей для сбора, найти базу для атаки"""
        if self._state.data.get_target_for_collecting_resource(self) is None:
            for enemy_base in sorted(self._state.data.get_enemy_motherships(self), key=lambda x: x.distance_to(self)):
                if enemy_base.is_alive:
                    self.target_for_attack = enemy_base
                    return True

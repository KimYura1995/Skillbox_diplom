# -*- coding: utf-8 -*-

from astrobox.space_field import SpaceField
from kim import KimDrone
from stage_03_harvesters.reaper import ReaperDrone
from stage_03_harvesters.driller import DrillerDrone
from stage_03_harvesters.vader import VaderDrone


if __name__ == '__main__':
    scene = SpaceField(
        speed=5,
        asteroids_count=15
    )
    swarm1 = [KimDrone() for _ in range(5)]
    swarm2 = [DrillerDrone() for _ in range(5)]
    # swarm3 = [VaderDrone() for _ in range(5)]
    # swarm4 = [ReaperDrone() for _ in range(5)]
    scene.go()

# Первый этап: зачёт!
# Второй этап: зачёт!
# Третий этап: зачёт!

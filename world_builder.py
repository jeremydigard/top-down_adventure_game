from __future__ import annotations
from dataclasses import dataclass
import random
import arcade
from navmesh import NavMesh, build_navmesh, is_walkable

from arme import Arme, Boomerang, Epee, WeaponContext, WeaponController
from constants import SCALE, TILE_SIZE
from helper import grid_to_pixels
from map import GridCell, Map, InvalidMapFileException
from monsters import *
from player import Player
from portail import Lever, Gate
from textures import (
    CRYSTAL_ANIMATION,
    TEXTURE_BUSH,
    TEXTURE_GRASS,
    TEXTURE_HOLE,
    TEXTURE_SIGN,
)


@dataclass(frozen=True)
class LoadedWorld:
    game_map: Map
    navmesh: NavMesh
    grounds: arcade.SpriteList
    trou: arcade.SpriteList
    walls: arcade.SpriteList
    levers: arcade.SpriteList
    open_gates: arcade.SpriteList
    closed_gates: arcade.SpriteList
    exits: arcade.SpriteList
    crystals: arcade.SpriteList
    mobs: arcade.SpriteList
    player_list: arcade.SpriteList
    weapons: arcade.SpriteList
    blob_vision_blockers: arcade.SpriteList
    player: Player
    boomerang: Boomerang
    epee: Epee
    weapon_controller: WeaponController

    @property
    def active_weapon(self) -> Arme:
        return self.weapon_controller.active_weapon

    @property
    def weapon_context(self) -> WeaponContext:
        return WeaponContext(
            player=self.player,
            walls=self.walls,
            mobs=self.mobs,
            levers=self.levers,
            crystals=self.crystals,
        )

class WorldBuilder:
    @staticmethod
    def build_from_map(game_map: Map, random_seed: random.Random | None = None) -> LoadedWorld:
        navmesh = build_navmesh(game_map)
        grounds = arcade.SpriteList(use_spatial_hash=True)
        trou = arcade.SpriteList(use_spatial_hash=True)
        walls = arcade.SpriteList(use_spatial_hash=True)
        levers = arcade.SpriteList(use_spatial_hash=True)
        open_gates = arcade.SpriteList(use_spatial_hash=True)
        closed_gates = arcade.SpriteList(use_spatial_hash=True)
        exits = arcade.SpriteList(use_spatial_hash=True)
        crystals = arcade.SpriteList(use_spatial_hash=True)
        mobs = arcade.SpriteList(use_spatial_hash=True)
        player_list = arcade.SpriteList(use_spatial_hash=False)
        weapons = arcade.SpriteList(use_spatial_hash=True)
        blob_vision_blockers = arcade.SpriteList(use_spatial_hash=True)

        WorldBuilder._populate_map_bound_sprites(
            game_map=game_map,
            navmesh=navmesh,
            grounds=grounds,
            trou=trou,
            walls=walls,
            levers=levers,
            closed_gates=closed_gates,
            exits=exits,
            crystals=crystals,
            mobs=mobs,
            blob_vision_blockers=blob_vision_blockers,
            random_seed=random_seed,
        )
        player = WorldBuilder._spawn_player(player_list, game_map)
        boomerang, epee, weapon_controller = WorldBuilder._spawn_weapons(weapons)

        return LoadedWorld(
            game_map=game_map,
            navmesh=navmesh,
            grounds=grounds,
            trou=trou,
            walls=walls,
            levers=levers,
            open_gates=open_gates,
            closed_gates=closed_gates,
            exits=exits,
            crystals=crystals,
            mobs=mobs,
            player_list=player_list,
            weapons=weapons,
            blob_vision_blockers=blob_vision_blockers,
            player=player,
            boomerang=boomerang,
            epee=epee,
            weapon_controller=weapon_controller,
        )

    @staticmethod
    def build_from_string(raw: str, random_seed: random.Random | None = None) -> LoadedWorld:
        return WorldBuilder.build_from_map(Map.from_string(raw), random_seed)

    @staticmethod
    def build_from_file(file_map: str, random_seed: random.Random | None = None) -> LoadedWorld:
        return WorldBuilder.build_from_map(Map.from_file(file_map), random_seed)

    @staticmethod
    def build(file_map: str, random_seed: random.Random | None = None) -> LoadedWorld:
        return WorldBuilder.build_from_file(file_map, random_seed)

    @staticmethod
    def _spawn_player(player_list: arcade.SpriteList, game_map: Map) -> Player:
        player = Player(
            center_x=grid_to_pixels(game_map.player_start_x),
            center_y=grid_to_pixels(game_map.player_start_y),
            scale = 0.95 * SCALE # pour éviter les bugs de PhysicsEngine quand le Player est entre deux buissons
        )
        player_list.append(player)
        return player

    @staticmethod
    def _spawn_weapons(weapons: arcade.SpriteList) -> tuple[Boomerang, Epee, WeaponController]:
        boomerang = Boomerang()
        epee = Epee()
        weapon_controller = WeaponController((boomerang, epee))

        for weapon in weapon_controller.weapons:
            for sprite in weapon.sprites:
                weapons.append(sprite)

        return boomerang, epee, weapon_controller


# faire test pour cette fonction, et pour la fonction compute_spinner_bounds
    @staticmethod
    def first_obstacle(game_map: Map, x: int, y: int, dx: int, dy: int) -> tuple[int, int] | None:
        """Depuis (x,y), avance en (dx,dy) et retourne la position du premier BUISSON."""
        nx, ny = x + dx, y + dy
        while 0 <= nx < game_map.width and 0 <= ny < game_map.height:
            if game_map.get(nx, ny) == GridCell.BUISSON:
                return (nx, ny)
            nx += dx
            ny += dy
        return None

# une property ici ?
    @staticmethod
    def compute_spinner_bounds( game_map: Map, x: int, y: int, horizontal: bool ) -> tuple[int, int]:
        """Calcule les limites min et max (en coordonnées grille) d'un spinner.

        Pour un spinner horizontal à la position (x, y) :
            - Cherche le premier buisson à gauche  → borne gauche  = buisson_x + 1
            - Cherche le premier buisson à droite → borne droite = buisson_x - 1
        Pour un spinner vertical à la position (x, y) :
            - Cherche le premier buisson en bas    → borne basse  = buisson_y + 1
            - Cherche le premier buisson en haut   → borne haute  = buisson_y - 1
        Si aucun obstacle n'est trouvé dans une direction, on utilise le bord de la map.

        Retourne (min_grid, max_grid) en coordonnées grille.
        """
        if horizontal:
            neg, pos, axis = (-1, 0), (1, 0), 0
            default_min, default_max = 0, game_map.width - 1
        else:
            neg, pos, axis = (0, -1), (0, 1), 1
            default_min, default_max = 0, game_map.height - 1

        obs_min = WorldBuilder.first_obstacle(game_map, x, y, *neg)
        obs_max = WorldBuilder.first_obstacle(game_map, x, y, *pos)

        if obs_min is None or obs_max is None :
            raise InvalidMapFileException("Position de Spinner invalide: les spinneurs doivent avoir un obstacle sur leur chemin.")

        min_grid = obs_min[axis] + 1 if obs_min is not None else default_min
        max_grid = obs_max[axis] - 1 if obs_max is not None else default_max


        return min_grid, max_grid

    @staticmethod
    def _populate_map_bound_sprites(
        game_map: Map,
        navmesh: NavMesh,
        grounds: arcade.SpriteList,
        trou: arcade.SpriteList,
        walls: arcade.SpriteList,
        levers: arcade.SpriteList,
        closed_gates: arcade.SpriteList,
        exits: arcade.SpriteList,
        crystals: arcade.SpriteList,
        mobs: arcade.SpriteList,
        blob_vision_blockers: arcade.SpriteList,
        random_seed: random.Random | None = None,
    ) -> None:
        lever_counter : int = 0
        gate_counter : int = 0


        for y in range(game_map.height):
            for x in range(game_map.width):
                px = grid_to_pixels(x)
                py = grid_to_pixels(y)

                grounds.append(
                    arcade.Sprite(
                        TEXTURE_GRASS,
                        scale=SCALE,
                        center_x=px,
                        center_y=py,
                    )
                )
                match game_map.get(x, y):

                    case GridCell.GRASS:
                        pass
                    case GridCell.BUISSON:
                        wall = arcade.Sprite(
                            TEXTURE_BUSH,
                            scale=SCALE,
                            center_x=px,
                            center_y=py,
                        )
                        walls.append(wall)
                        blob_vision_blockers.append(wall)

                    case GridCell.CRYSTAL:
                        crystals.append(
                            arcade.TextureAnimationSprite(
                                animation=CRYSTAL_ANIMATION,
                                scale=SCALE,
                                center_x=px,
                                center_y=py,
                            )
                        )

                    case GridCell.SPINNEUR_HORIZONTAL:
                        mobs.append(
                            SpinnerHorizontal(
                                grid_x=x,
                                grid_y=y,
                                game_map=game_map,
                            )
                        )

                    case GridCell.SPINNEUR_VERTICAL:
                        mobs.append(
                            SpinnerVertical(
                                grid_x=x,
                                grid_y=y,
                                game_map=game_map,
                            )
                        )

                    case GridCell.BAT:
                        mobs.append(
                            Bat(
                                center_x=px,
                                center_y=py,
                                world_width=game_map.width * TILE_SIZE,
                                world_height=game_map.height * TILE_SIZE,
                                rng=random_seed,
                            )
                        )

                    case GridCell.TROU:
                        trou.append(
                            arcade.Sprite(
                                TEXTURE_HOLE,
                                scale=SCALE,
                                center_x=px,
                                center_y=py,
                            )
                        )
                    case GridCell.BLOB:
                        mobs.append(
                            Blob( # jsais pas c quoi le meix entre vect2 et juste x et y
                                origine=arcade.Vec2(px, py),
                                navmesh=navmesh,
                                possible_destinations=Blob.patrol_destinations(
                                    game_map,
                                    x,
                                    y,
                                    is_walkable_for_blob=is_walkable,
                                    navmesh=navmesh,
                                ),
                                vision_blockers=blob_vision_blockers,
                                sight_radius=100,
                                rng=random_seed,
                            )
                        )
                    case GridCell.LEVER:
                        if (x,y) not in game_map.switch_by_coords:
                            raise InvalidMapFileException(f"Levier à ({x}, {y}) n'est pas présent dans la config.")
                        lever = game_map.switch_by_coords[(x,y)]
                        lever_counter += 1
                        levers.append(
                            Lever(
                                center_x=px,
                                center_y=py,
                                scale=0.125*SCALE,
                                id=lever.id,
                                state=lever.state,
                            )
                        )
                    case GridCell.GATE:
                        if (x,y) not in game_map.gates_by_coords:
                            raise InvalidMapFileException(f"Portail à ({x}, {y}) n'est pas présent dans la config.")
                        gate_config = game_map.gates_by_coords[(x,y)]
                        gate_counter += 1
                        gate = Gate(
                            center_x=px,
                            center_y=py,
                            scale=SCALE,
                            open_conditions=gate_config.open_if,
                        )
                        closed_gates.append(gate)
                        blob_vision_blockers.append(gate)

                    case GridCell.EXIT:
                        exits.append(
                            arcade.Sprite(
                                TEXTURE_SIGN,
                                scale=SCALE,
                                center_x=px,
                                center_y=py,
                            )
                        )

                    case _:
                        raise InvalidMapFileException(f"Symbole de map inconnu à ({x}, {y}): {game_map.get(x, y)}")

        if lever_counter != len(game_map.switch_by_coords):
            raise InvalidMapFileException("Un levier de la section config n'est pas présent dans la map")

        if gate_counter != len(game_map.gates_by_coords):
            raise InvalidMapFileException("Un portail de la section config n'est pas présent dans la map")

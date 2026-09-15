from collections.abc import Iterable
from typing import Final
import math
from pathlib import Path
import arcade

from constants import PLAYER_HEALTH, SCALE, SECONDS_PER_FRAME, TILE_SIZE
from textures import CRYSTAL_ANIMATION, CRYSTAL_SOUND, DAMAGE_SOUND, HEALTH_BAR_TEXTURE, HEALTH_TEXTURE
from arme import CollectCrystal, HitTarget, ToggleLever, WeaponEffect
from map import Map
from world_builder import WorldBuilder, LoadedWorld
from player import KEY_TO_DIRECTION

if not arcade.timings_enabled():
    # Nécessaire pour arcade.get_fps(), utilisé par l'affichage debug de l'UI.
    arcade.enable_timings()


class GameView(arcade.View):

    world: Final[LoadedWorld]
    camera_game: Final[arcade.camera.Camera2D]
    camera_UI: Final[arcade.camera.Camera2D]
    world_width: Final[int]
    world_height: Final[int]
    physics_engine: arcade.PhysicsEngineSimple
    __lever_states: dict[str, bool]
    __file_map: Final[str | None]
    __show_hitboxes: bool
    __score: int
    __health: int
    __ui_sprites: arcade.SpriteList
    __score_text: arcade.Text
    __fps_text: arcade.Text

    def __init__(self, loaded_world: LoadedWorld, file_map: str | None = None) -> None:
        super().__init__()

        self.window.set_vsync(False)
        self.window.set_update_rate(SECONDS_PER_FRAME)
        self.window.set_draw_rate(SECONDS_PER_FRAME)
        self.__file_map = file_map
        self.world = loaded_world
        game_map = loaded_world.game_map

        self.world_width = game_map.width * TILE_SIZE
        self.world_height = game_map.height * TILE_SIZE

        self.camera_game = arcade.camera.Camera2D()
        self.camera_UI = arcade.camera.Camera2D()
        self.__init_ui()

        self.__lever_states = {lever.id :lever.state for lever in self.world.levers}

        self._move_gates_to_correct_spritelist(self.world.closed_gates, self.world.open_gates)

        obstacles = arcade.SpriteList()
        obstacles.extend(self.world.walls)
        obstacles.extend(self.world.closed_gates)

        self.physics_engine = arcade.PhysicsEngineSimple(
            self.world.player,
            obstacles
        )

        self.__show_hitboxes = False

    @staticmethod
    def from_file(file_map: str) -> GameView:
        return GameView(WorldBuilder.build_from_file(file_map), file_map)

    @staticmethod
    def from_map(game_map: Map) -> GameView:
        return GameView(WorldBuilder.build_from_map(game_map))

    @staticmethod
    def from_string(raw_map: str) -> GameView:
        return GameView.from_map(Map.from_string(raw_map))

    @property
    def file_map(self) -> str | None:
        return self.__file_map

    @property
    def score(self) -> int:
        return self.__score

    @property
    def health(self) -> int:
        return self.__health

    def __init_ui(self) -> None:
        self.__health = PLAYER_HEALTH
        self.__score = 0
        self.__ui_sprites = arcade.SpriteList()
        self.__ui_sprites.append(arcade.Sprite(
            HEALTH_TEXTURE,
            scale=SCALE,
            center_x=64,
            center_y=self.window.height - 15,
        ))
        self.__ui_sprites.append(arcade.Sprite(
            HEALTH_BAR_TEXTURE,
            scale=SCALE,
            center_x=64,
            center_y=self.window.height - 16,
        ))
        self.__ui_sprites.append(arcade.Sprite(
            CRYSTAL_ANIMATION.keyframes[0].texture,
            scale=0.8 * SCALE,
            center_x=150,
            center_y=self.window.height - 20,
        ))
        self.__score_text = arcade.Text(
            text=f"Score: {self.__score}",
            x=164,
            y=self.window.height - 4,
            color=arcade.color.BLIZZARD_BLUE,
            font_size=15,
            bold=True,
            anchor_x="left",
            anchor_y="top",
        )
        self.__fps_text = arcade.Text(
            text=f"fps: {round(arcade.get_fps())}",
            x=self.window.width - 80,
            y=self.window.height - 4,
            color=arcade.color.BLIZZARD_BLUE,
            font_size=15,
            bold=True,
            anchor_x="left",
            anchor_y="top",
        )

    def _handle_mob_collision(self) -> None:
        for mob in arcade.check_for_collision_with_list(self.world.player, self.world.mobs):
            self._handle_player_damage(mob.contact_damage)
            return

    def _handle_hole_collision(self) -> None:
        """
        Gère la collision du joueur avec les trous.
        Le joueur tombe s'il est à une demi grille du trou.

        """
        player = self.world.player
        nearby_holes = arcade.check_for_collision_with_list(player, self.world.trou)

        for hole in nearby_holes:
            distance = math.hypot(
                player.center_x - hole.center_x,
                player.center_y - hole.center_y,
            )
            if distance <= TILE_SIZE // 2:
                self._handle_player_death()

    def _collect_crystal(self, crystal: arcade.Sprite) -> None:
        if crystal in self.world.crystals:
            crystal.remove_from_sprite_lists()
            self.__score += 1
            self.__score_text.text = f"Score: {self.__score}"
            arcade.play_sound(CRYSTAL_SOUND)

    def _collect_crystals_from(self, sprite: arcade.Sprite) -> None:
        """Collecte tous les cristaux en collision avec le sprite donné."""
        for crystal in arcade.check_for_collision_with_list(sprite, self.world.crystals):
            self._collect_crystal(crystal)

    def _handle_crystal_collection(self) -> None:
        """Gère la collecte des cristaux par le joueur."""
        self._collect_crystals_from(self.world.player)

    def _update_physics_engine(self) -> None:
        obstacles = arcade.SpriteList()
        obstacles.extend(self.world.walls)
        obstacles.extend(self.world.closed_gates)
        self.physics_engine = arcade.PhysicsEngineSimple(self.world.player, obstacles)

    def _check_gate_states(self) -> None:
        """
        Vérifie si les portails doivent s'ouvrir ou fermer, en vérifiant les conditions de la config.
        Lance le changement d'état des portails ainsi que la mise à jour de l'engin de Physique.
        Pour réduire les calculs inutiles, cette fonction n'est que appelée lorsqu'un levier change d'état.
        """
        gates_opening = self._move_gates_to_correct_spritelist(self.world.closed_gates, self.world.open_gates)
        gates_closing = self._move_gates_to_correct_spritelist(self.world.open_gates, self.world.closed_gates)

        gates_changing = gates_opening or gates_closing

        if gates_changing:
            self._update_physics_engine()


    def _move_gates_to_correct_spritelist(self, from_list: arcade.SpriteList, to_list: arcade.SpriteList) -> bool:
        """
        Déplace les portails d'une liste qui ont changé d'état vers un autre liste.
        Retourne True si au moins un élément à été déplacé.
        """
        gates_to_move = [gate for gate in from_list if gate.update_state(self.__lever_states)]

        for gate in gates_to_move:
            from_list.remove(gate)
            to_list.append(gate)
            if gate.is_closed:
                if gate not in self.world.blob_vision_blockers:
                    self.world.blob_vision_blockers.append(gate)
            elif gate in self.world.blob_vision_blockers:
                self.world.blob_vision_blockers.remove(gate)

        return bool(gates_to_move) # False ssi la liste est vide

    def _apply_weapon_effects(self, effects: Iterable[WeaponEffect]) -> None:
        switch_change: bool = False

        for effect in effects:
            match effect:
                case HitTarget(target=target):
                    target.on_weapon_hit()
                case CollectCrystal(crystal=crystal):
                    self._collect_crystal(crystal)
                case ToggleLever(lever=lever):
                    lever.switch_state()
                    switch_change = True
                    self.__lever_states[lever.id] = lever.state

        if switch_change:
            self._check_gate_states()

    def _handle_player_damage(self, amount: int = 1) -> None:
        if amount <= 0:
            return

        self.__health -= amount
        health_sprite = self.__ui_sprites[0]
        health_sprite.center_x -= 4 * amount
        if self.__health <= 0:
            self._handle_player_death()
        arcade.play_sound(DAMAGE_SOUND)

    def _handle_player_death(self) -> None:
        if self.__file_map is None:
            self.window.show_view(GameView.from_map(self.world.game_map))
        else:
            self.window.show_view(GameView.from_file(self.__file_map))

    def _resolve_next_map_path(self, next_map: str) -> str:
        """
        Les chemins `next_map` sont interprétés relativement au fichier de map
        courant, pour pouvoir déplacer un dossier de maps sans réécrire la config.
        """
        if self.__file_map is None:
            return next_map
        return str(Path(self.__file_map).parent / next_map)

    def _handle_exit_collision(self) -> None:
        """
        Charge la map suivante lorsque le joueur touche l'unique sortie.

        Le parseur garantit que `next_map` et la sortie `E` apparaissent ensemble;
        le test `None` garde seulement cette méthode robuste si elle est appelée
        sur une map sans sortie.
        """
        next_map = self.world.game_map.next_map
        if next_map is None:
            return
        if arcade.check_for_collision_with_list(self.world.player, self.world.exits):
            self.window.show_view(GameView.from_file(self._resolve_next_map_path(next_map)))

    def on_update(self, delta_time: float) -> None:
        """
        Called once per frame, before drawing.
        This is where in-world time "advances", or "ticks".
        """
        if self.world.weapon_controller.locks_player:
            self.world.player.change_x = 0
            self.world.player.change_y = 0
        else:
            self.world.player.update(delta_time)

        self.physics_engine.update()

        player_position = self.world.player.position
        for mob in self.world.mobs:
            mob.update_monster(delta_time, player_position)

        weapon_effects = self.world.weapon_controller.update_weapon(self.world.weapon_context, delta_time)
        self._apply_weapon_effects(weapon_effects)

        self.world.crystals.update_animation(delta_time)
        self.world.mobs.update_animation(delta_time)
        self.world.player_list.update_animation(delta_time)
        self.world.weapons.update_animation(delta_time)
        self.__update_game_camera()
        self.__fps_text.text = f"fps: {round(arcade.get_fps())}"

        self._handle_hole_collision()
        self._handle_mob_collision()
        self._handle_crystal_collection()

        self._handle_exit_collision()

    def __update_game_camera(self) -> None:
        player_x, player_y = self.world.player.position
        half_window_width = self.window.width / 2
        half_window_height = self.window.height / 2

        min_camera_x = half_window_width
        max_camera_x = self.world_width - half_window_width
        camera_x = max(min_camera_x, min(player_x, max_camera_x))

        min_camera_y = half_window_height
        max_camera_y = self.world_height - half_window_height
        camera_y = max(min_camera_y, min(player_y, max_camera_y))

        if self.world_width < self.window.width:
            camera_x = self.world_width / 2
        if self.world_height < self.window.height:
            camera_y = self.world_height / 2

        self.camera_game.position = arcade.Vec2(camera_x, camera_y)

    def on_draw(self) -> None:
        self.clear()

        with self.camera_game.activate():
            self.world.grounds.draw()
            self.world.trou.draw()
            self.world.walls.draw()
            self.world.levers.draw()
            self.world.open_gates.draw()
            self.world.closed_gates.draw()
            self.world.exits.draw()
            self.world.crystals.draw()
            self.world.mobs.draw()
            self.world.player_list.draw()
            self.world.weapons.draw()

            if self.__show_hitboxes:
                self.world.grounds.draw_hit_boxes(color=arcade.color.LIME_GREEN)
                self.world.walls.draw_hit_boxes(color=arcade.color.BLUE)
                self.world.player.draw_hit_box(color=arcade.color.BLACK)
                self.world.active_weapon.draw_hit_box(color=arcade.color.GREEN)
                self.world.crystals.draw_hit_boxes(color=arcade.color.PINK)
                self.world.mobs.draw_hit_boxes(color=arcade.color.YELLOW)
                self.world.exits.draw_hit_boxes(color=arcade.color.WHITE)
                self.world.levers.draw_hit_boxes(color=arcade.color.RED)
                self.world.open_gates.draw_hit_boxes(color=arcade.color.ORANGE)
                self.world.closed_gates.draw_hit_boxes(color=arcade.color.ORANGE)

        with self.camera_UI.activate():
            self.__score_text.draw()
            self.__ui_sprites.draw()
            self.__fps_text.draw()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        """Called when the user presses a key on the keyboard."""
        player = self.world.player

        if symbol in KEY_TO_DIRECTION:
            player.handle_direction_key_press(KEY_TO_DIRECTION[symbol])
        else:
            match symbol:
                case arcade.key.ESCAPE:
                    self._handle_player_death()
                case arcade.key.D:
                    self.world.weapon_controller.use_active_weapon(self.world.weapon_context)
                case arcade.key.R:
                    self.world.weapon_controller.switch_weapon()
                case arcade.key.H:
                    self.__show_hitboxes = not self.__show_hitboxes
                case _:
                    pass


    def on_key_release(self, symbol: int, modifiers: int) -> None:
        """Called when the user releases a key on the keyboard."""
        if symbol in KEY_TO_DIRECTION:
            self.world.player.handle_direction_key_release(KEY_TO_DIRECTION[symbol])

    def __repr__(self) -> str:
        return (
            f"GameView("
            f"file_map={self.__file_map!r}, "
            f"world_size=({self.world_width}, {self.world_height}), "
            f"score={self.__score}, "
            f"health={self.__health}"
            ")"
        )

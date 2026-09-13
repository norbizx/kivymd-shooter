import json
import os
from random import randint

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDRectangleFlatButton
from kivy import platform
from kivy.core.window import Window
from kivy.uix.image import Image
from kivymd.uix.widget import MDWidget

FPS = 60
BULLET_SPEED = dp(10)
SHIP_SPEED = dp(10)
ENEMY_SPEED = dp(3)
ENEMY_SPAWN_INTERVAL = 1.5
DIR_UP = 1
DIR_DOWN = -1

BULLET_SPAWN_OFFSET = dp(5)

RECORD_FILE = "record.json"
SETTINGS_FILE = "settings.json"

SKINS = [
    {"name": "Классика", "source": "assets/images/rocket.png"},
    {"name": "Скин 2", "source": "assets/images/rocket_2.png"},
    {"name": "Скин 3", "source": "assets/images/rocket_3.png"},
]

DEFAULT_SKIN = SKINS[0]["source"]


def loadRecord():
    if os.path.exists(RECORD_FILE):
        try:
            with open(RECORD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return int(data.get("record", 0))
        except (json.JSONDecodeError, ValueError, OSError):
            return 0
    return 0


def saveRecord(value):
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump({"record": value}, f)


def loadSelectedSkin():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("skin", DEFAULT_SKIN)
        except (json.JSONDecodeError, OSError):
            return DEFAULT_SKIN
    return DEFAULT_SKIN


def saveSelectedSkin(source):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"skin": source}, f)


class Shot(MDWidget):
    def __init__(self, direction, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction

    def move(self):
        self.y += BULLET_SPEED * self.direction


class MainScreen(MDScreen):
    record_text = StringProperty("Рекорд: 0")

    def on_pre_enter(self, *args):
        record = loadRecord()
        self.record_text = f"Рекорд: {record}"
        return super().on_pre_enter(*args)


class SkinsScreen(MDScreen):
    skins = ListProperty(SKINS)

    def on_pre_enter(self, *args):
        container = self.ids.skins_container
        container.clear_widgets()
        for skin in self.skins:
            btn = MDRectangleFlatButton(
                text=skin["name"],
                pos_hint={"center_x": 0.5},
                size_hint_x=0.8,
            )
            btn.bind(on_press=lambda inst, s=skin["source"]: self.selectSkin(s))
            container.add_widget(btn)
        return super().on_pre_enter(*args)

    def selectSkin(self, source):
        saveSelectedSkin(source)
        self.manager.current = 'main'


class Ship(Image):
    def __init__(self, direction=DIR_UP, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction
        self.game = None

    def moveLeft(self):
        self.pos[0] -= SHIP_SPEED

    def moveRight(self):
        self.pos[0] += SHIP_SPEED

    def shot(self):
        if self.game is None:
            return
        shot = Shot(self.direction)
        shot.center_x = self.center_x

        if self.direction == DIR_UP:
            shot.center_y = self.top - BULLET_SPAWN_OFFSET
        else:
            shot.center_y = self.y + BULLET_SPAWN_OFFSET

        self.game.bullets.append(shot)
        self.game.ids.front.add_widget(shot)

    def update(self):
        ...


class PlayerShip(Ship):
    def __init__(self, direction=DIR_UP, **kwargs):
        super().__init__(**kwargs)

    def applySkin(self):
        self.source = loadSelectedSkin()

    def update(self, keys):
        for key in keys:
            if keys[key] == True:
                if key == "left" and self.x > 0:
                    self.moveLeft()
                if key == "right" and self.right < Window.size[0]:
                    self.moveRight()
                if key == "shot":
                    self.shot()
                    keys[key] = False


class EnemyShip(Ship):
    def __init__(self, direction=DIR_UP, **kwargs):
        super().__init__(direction=DIR_DOWN, **kwargs)
        self.frame = 0
        self.health = 1

    def takeDamage(self, dmg=1):
        self.health -= dmg
        if self.health <= 0:
            self.destroy(killed=True)

    def destroy(self, killed=False):
        if self.parent:
            self.parent.remove_widget(self)
        if self.game and self in self.game.enemyShips:
            self.game.enemyShips.remove(self)
        if killed and self.game:
            self.game.addScore(1)

    def move(self):
        self.y += ENEMY_SPEED * self.direction


class GameScreen(MDScreen):
    score = NumericProperty(0)
    score_text = StringProperty("0")
    paused = BooleanProperty(False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.eventkeys = {}
        self.bullets = []
        self.enemyShips = []
        self.ship = self.ids.ship
        self.ship.game = self
        self.spawnEvent = None
        self.updateEvent = None

        Window.bind(on_key_down=self.on_key_down)
        Window.bind(on_key_up=self.on_key_up)

    KEY_MAP = {
        276: "left",
        275: "right",
        32: "shot",
        273: "shot",
    }

    def on_key_down(self, window, key, *args):
        if self.paused:
            return
        action = self.KEY_MAP.get(key)
        if action:
            self.pressKey(action)

    def on_key_up(self, window, key, *args):
        action = self.KEY_MAP.get(key)
        if action:
            self.releaseKey(action)

    def on_pre_enter(self, *args):
        self.score = 0
        self.score_text = "0"
        self.paused = False
        self.ship.applySkin()
        return super().on_pre_enter(*args)

    def on_enter(self, *args):
        self.startGame()
        return super().on_enter(*args)

    def on_leave(self, *args):
        self.stopEvents()

        for enemy in self.enemyShips[:]:
            if enemy.parent:
                enemy.parent.remove_widget(enemy)
        self.enemyShips.clear()

        for bullet in self.bullets[:]:
            if bullet.parent:
                bullet.parent.remove_widget(bullet)
        self.bullets.clear()

        return super().on_leave(*args)

    def startGame(self):
        self.updateEvent = Clock.schedule_interval(self.update, 1 / FPS)
        self.spawnEvent = Clock.schedule_interval(self.spawnEnemy, ENEMY_SPAWN_INTERVAL)
        self.spawnEnemy(0)

    def stopEvents(self):
        if self.updateEvent:
            self.updateEvent.cancel()
            self.updateEvent = None
        if self.spawnEvent:
            self.spawnEvent.cancel()
            self.spawnEvent = None

    def show_menu(self):
        """Вызывается кнопкой паузы"""
        self.paused = True
        self.eventkeys.clear()  # чтобы корабль не "залипал" в движении при паузе
        self.stopEvents()

    def resumeGame(self):
        self.paused = False
        self.startGame()

    def exitToMenu(self):
        self.paused = False
        self.manager.current = 'main'

    def addScore(self, amount=1):
        self.score += amount
        self.score_text = str(self.score)

        record = loadRecord()
        if self.score > record:
            saveRecord(self.score)

    def spawnEnemy(self, dt):
        ship = EnemyShip()
        ship.game = self
        ship.pos = (randint(0, int(Window.size[0] - ship.width)), Window.size[1])
        self.enemyShips.append(ship)
        self.ids.front.add_widget(ship)

    def update(self, dt):
        self.ship.update(self.eventkeys)

        for bullet in self.bullets[:]:
            bullet.move()

            if bullet.top < 0 or bullet.y > Window.size[1]:
                self.ids.front.remove_widget(bullet)
                self.bullets.remove(bullet)
                continue

            for enemy in self.enemyShips[:]:
                if bullet.collide_widget(enemy):
                    enemy.takeDamage(1)
                    self.ids.front.remove_widget(bullet)
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)
                    break

        for enemy in self.enemyShips[:]:
            enemy.move()
            if enemy.top < 0:
                self.ids.front.remove_widget(enemy)
                self.enemyShips.remove(enemy)

    def pressKey(self, key):
        if self.paused:
            return
        self.eventkeys[key] = True

    def releaseKey(self, key):
        self.eventkeys[key] = False

    def moveLeft(self):
        pass

    def moveRight(self):
        pass

    def shot(self):
        pass


class ShooterApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Orange"

        self.sm = MDScreenManager()

        self.sm.add_widget(MainScreen(name='main'))
        self.sm.add_widget(SkinsScreen(name='skins'))
        self.sm.add_widget(GameScreen(name='game'))

        return self.sm


if platform != 'android':
    Window.size = (450, 900)
    Window.top = 100
    Window.left = 600

app = ShooterApp()
app.run()
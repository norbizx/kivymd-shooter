import json
import os
import webbrowser
from random import randint

from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDRectangleFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
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

# Поклади свій трек сюди (mp3 або ogg; ogg надійніше працює на Android)
MUSIC_FILE = "assets/sounds/music.mp3"
DEFAULT_MUSIC_VOLUME = 0.4

# Звук пострілу (пробіл / кнопка "вистрел")
SHOT_SOUND_FILE = "assets/sounds/shot.mp3"
SHOT_SOUND_VOLUME = 1.0

# Картинка пульки — встав свій файл сюди
BULLET_IMAGE = "assets/images/bullet.png"

# Посилання, яке відкривається при кліку на лівий банер
BANNER_URL = "https://logikaschool.com/"

SKINS = [
    {"name": "Класика", "source": "assets/images/rocket.png"},
    {"name": "Скін 2", "source": "assets/images/rocket_2.png"},
    {"name": "Скін 3", "source": "assets/images/rocket_3.png"},
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


def loadSettings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def saveSettings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def loadSelectedSkin():
    return loadSettings().get("skin", DEFAULT_SKIN)


def saveSelectedSkin(source):
    settings = loadSettings()
    settings["skin"] = source
    saveSettings(settings)


def loadMusicEnabled():
    return bool(loadSettings().get("music", True))


def saveMusicEnabled(value):
    settings = loadSettings()
    settings["music"] = bool(value)
    saveSettings(settings)


def loadMusicVolume():
    try:
        value = float(loadSettings().get("music_volume", DEFAULT_MUSIC_VOLUME))
    except (TypeError, ValueError):
        value = DEFAULT_MUSIC_VOLUME
    return min(1.0, max(0.0, value))


def saveMusicVolume(value):
    settings = loadSettings()
    settings["music_volume"] = float(value)
    saveSettings(settings)


class Shot(Image):
    """Пулька гравця/ворога. Картинка задається в .kv (BULLET_IMAGE)."""

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


class SkinCard(MDCard):
    """Картка скіна: картинка + назва. Клік = вибір скіна."""

    def __init__(self, skin, selected=False, onSelect=None, **kwargs):
        super().__init__(**kwargs)
        self.skin = skin
        self.onSelect = onSelect

        self.orientation = "vertical"
        self.padding = dp(10)
        self.spacing = dp(5)
        self.size_hint = (None, None)
        self.size = (dp(150), dp(190))
        self.radius = [dp(16)]
        self.md_bg_color = (0.28, 0.08, 0.18, 1)
        self.ripple_behavior = True

        self.line_color = (1, 0.6, 0.2, 1) if selected else (0.5, 0.5, 0.5, 0.5)
        self.line_width = dp(2) if selected else dp(1)

        self.add_widget(Image(
            source=skin["source"],
            allow_stretch=True,
            keep_ratio=True,
            size_hint_y=0.75,
        ))
        self.add_widget(MDLabel(
            text=(f"{skin['name']} ✔" if selected else skin["name"]),
            halign="center",
            font_style="Subtitle1",
            size_hint_y=0.25,
        ))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.onSelect:
                self.onSelect(self.skin["source"])
            return True
        return super().on_touch_down(touch)


class SkinsScreen(MDScreen):
    skins = ListProperty(SKINS)

    def on_pre_enter(self, *args):
        self.buildCards()
        return super().on_pre_enter(*args)

    def buildCards(self):
        current = loadSelectedSkin()
        container = self.ids.skins_container
        container.clear_widgets()
        for skin in self.skins:
            container.add_widget(SkinCard(
                skin=skin,
                selected=(skin["source"] == current),
                onSelect=self.selectSkin,
            ))

    def selectSkin(self, source):
        saveSelectedSkin(source)
        self.buildCards()
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

        app = MDApp.get_running_app()
        if app:
            app.playShotSound()

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
        self.dialog = None

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
        self.closeDialog()
        self.clearGameObjects()
        return super().on_leave(*args)

    def clearGameObjects(self):
        for enemy in self.enemyShips[:]:
            if enemy.parent:
                enemy.parent.remove_widget(enemy)
        self.enemyShips.clear()

        for bullet in self.bullets[:]:
            if bullet.parent:
                bullet.parent.remove_widget(bullet)
        self.bullets.clear()

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
        """Викликається кнопкою паузи"""
        self.paused = True
        self.eventkeys.clear()
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
                continue

            if enemy.collide_widget(self.ship):
                self.playerDied()
                return

    def playerDied(self):
        self.stopEvents()
        self.eventkeys.clear()
        self.clearGameObjects()

        record = loadRecord()
        if self.score > record:
            saveRecord(self.score)

        self.showGameOverDialog()

    def showGameOverDialog(self):
        if self.dialog:
            return

        self.dialog = MDDialog(
            title="Ти помер!",
            text=f"Рахунок: {self.score}",
            auto_dismiss=False,
            buttons=[
                MDRectangleFlatButton(
                    text="ГРАТИ ЗНОВУ",
                    on_release=lambda inst: self.restartGame(),
                ),
                MDRectangleFlatButton(
                    text="У МЕНЮ",
                    on_release=lambda inst: self.goToMenu(),
                ),
            ],
        )
        self.dialog.open()

    def closeDialog(self):
        if self.dialog:
            self.dialog.dismiss()
            self.dialog = None

    def restartGame(self):
        self.closeDialog()

        self.score = 0
        self.score_text = "0"
        self.paused = False
        self.eventkeys.clear()

        self.startGame()

    def goToMenu(self):
        self.closeDialog()
        self.manager.current = 'main'

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
    music_on = BooleanProperty(True)
    music_volume = NumericProperty(DEFAULT_MUSIC_VOLUME)

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Orange"

        self.music = None
        self.shot_sound = None
        self.music_on = loadMusicEnabled()
        self.music_volume = loadMusicVolume()

        self.sm = MDScreenManager()

        self.sm.add_widget(MainScreen(name='main'))
        self.sm.add_widget(SkinsScreen(name='skins'))
        self.sm.add_widget(GameScreen(name='game'))

        return self.sm

    def on_start(self):
        self.initMusic()
        self.initSounds()
        return super().on_start()

    # --- МУЗИКА ---

    def initMusic(self):
        if not os.path.exists(MUSIC_FILE):
            print(f"[МУЗИКА] Файл не знайдено: {MUSIC_FILE}")
            return

        self.music = SoundLoader.load(MUSIC_FILE)
        if not self.music:
            print(f"[МУЗИКА] Не вдалося завантажити: {MUSIC_FILE}")
            return

        self.music.loop = True
        self.music.volume = self.music_volume if self.music_on else 0

        if self.music_on:
            self.music.play()

    def toggleMusic(self):
        """Кнопка увімк./вимк. Не чіпає значення повзунка, лише грає/зупиняє."""
        self.music_on = not self.music_on
        saveMusicEnabled(self.music_on)

        if not self.music:
            return

        if self.music_on:
            self.music.volume = self.music_volume
            if self.music.state != "play":
                self.music.play()
        else:
            self.music.stop()

    def setMusicVolume(self, value):
        """Викликається повзунком гучності в реальному часі."""
        value = min(1.0, max(0.0, float(value)))
        self.music_volume = value
        saveMusicVolume(value)

        if not self.music:
            return

        if not self.music_on:
            self.music_on = True
            saveMusicEnabled(True)
            self.music.volume = value
            if self.music.state != "play":
                self.music.play()
        else:
            self.music.volume = value

    def on_pause(self):
        if self.music and self.music.state == "play":
            self.music.stop()
        return True

    def on_resume(self):
        if self.music and self.music_on:
            self.music.volume = self.music_volume
            self.music.play()

    def on_stop(self):
        if self.music:
            self.music.stop()
            self.music.unload()
        return super().on_stop()

    # --- ЗВУК ПОСТРІЛУ ---

    def initSounds(self):
        if not os.path.exists(SHOT_SOUND_FILE):
            print(f"[ЗВУК] Файл не знайдено: {SHOT_SOUND_FILE}")
            self._shot_sound_ok = False
            return
        self._shot_sound_ok = True
        # Список активних звуків пострілу, щоб вони не збирались сміттярем,
        # поки не дограють
        self._active_shot_sounds = []

    def playShotSound(self):
        """
        Кожен постріл створює СВІЙ окремий Sound і програє його незалежно
        від попередніх - тому звуки накладаються один на одного, а не
        обривають попередній (як просив користувач: "щоб клалось зверху").
        """
        if not getattr(self, "_shot_sound_ok", False):
            return

        sound = SoundLoader.load(SHOT_SOUND_FILE)
        if not sound:
            return

        sound.volume = SHOT_SOUND_VOLUME
        self._active_shot_sounds.append(sound)

        def cleanup(*args):
            if sound in self._active_shot_sounds:
                self._active_shot_sounds.remove(sound)
            sound.unload()

        sound.bind(on_stop=cleanup)
        sound.play()

    # --- БАНЕР ---

    def openBannerLink(self):
        """Відкриває сайт у браузері при кліку на лівий банер."""
        webbrowser.open(BANNER_URL)


if platform != 'android':
    Window.size = (450, 900)
    Window.top = 100
    Window.left = 600

app = ShooterApp()
app.run()
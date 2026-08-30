from random import randint

from kivy.clock import Clock
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivy import platform
from kivy.core.window import Window
from kivy.uix.image import Image
from kivymd.uix.widget import MDWidget

FPS = 60
BULLET_SPEED = dp(10)
SHIP_SPEED = dp(10)
DIR_UP = 1
DIR_DOWN = -1

class Shot(MDWidget):
    def __init__(self,direction, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction
class MainScreen(MDScreen):
    ...



class Ship(Image):
    def __init__(self, direction=DIR_UP, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction

    def moveLeft(self):  # todo
        self.pos[0] += SHIP_SPEED

    def moveRight(self):  # todo
        self.pos[0] -= SHIP_SPEED

    def shot(self):  # todo
        shot = Shot(self.direction)
        shot.center_x = self.center_x
        shot.center_y = self.top
        self.parent.parent.parent.parent.bulletsappend(shot)
        self.parrent.add_widget(shot)
    def update(self):
        ...

class PlayerShip(Ship):
    def __init__(self, direction=DIR_UP, **kwargs):
        super().__init__(**kwargs)

    def update(self, keys):
        for key in keys:
            if keys[key] == True:
                if key == "left" and self.center_x > 0:
                    self.moveLeft()
                if key == "right" and self.center_x > 0:
                    self.moveRight()
                if key == "shot":
                    self.shot()
                    keys[key] = False

class EnemyShip(Ship):
    def __init__(self, direction=DIR_UP, **kwargs):
        super().__init__(direction=DIR_DOWN, **kwargs)
        self.frame = 0


class GameScreen(MDScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.eventkeys = {}
        self.bullets = []
        self.enemyShips = []
        self.ship = self.ids.ship

        #Window.bind(on_key_down=)
        #Window.bind(on_key_up=)

    def on_enter(self,*args):
        self.updateEvent = Clock.schedule_interval(self.update, 1 / FPS)

        ship = EnemyShip()
        ship.pos = (randint(0,int(Window.size[0] - ship.size[0]))), Window.size[1]
        self.enemyShips.append(ship)
        self.ids.front.add_widget(ship)

        return super().on_enter(*args)


    def update(self,dt): #todo корабль управлять
        self.ship.update(self.eventkeys)

        #todo logic enemy
    def pressKey(self, key):   #todo
        self.eventkeys[key] = True

    def releaseKey(self, key):  # todo
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
        self.sm.add_widget(GameScreen(name='game'))

        return self.sm


if platform != 'android':
    Window.size = (450, 900)
    Window.top = 100
    Window.left = 600

app = ShooterApp()
app.run()

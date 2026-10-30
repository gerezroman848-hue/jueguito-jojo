import math
import random
import json
from array import array
from pathlib import Path
from datetime import datetime
import pygame

# DEFENSA PLANETARIA - versión ampliada
# Instalar: python -m pip install pygame
# Ejecutar: python defensa_planetaria.py

pygame.init()

WIDTH, HEIGHT = 900, 650
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("DEFENSA PLANETARIA  |  Arcade espacial")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("consolas", 24)
SMALL = pygame.font.SysFont("consolas", 17)
BIG = pygame.font.SysFont("consolas", 42, bold=True)

WHITE = (240, 245, 255)
CYAN = (70, 220, 255)
RED = (255, 75, 75)
YELLOW = (255, 220, 70)
GREEN = (70, 235, 120)
DARK = (5, 8, 25)
GAME_DURATION = 90  # duración total de la partida
BOSS_DURATION = 30  # el jefe aparece durante los últimos 30 segundos
BOSS_START = GAME_DURATION - BOSS_DURATION
MAX_RECORDS = 10
SCORE_FILE = Path(__file__).with_name("defensa_planetaria_records.json")


# Efectos de sonido originales sintetizados al iniciar. No requiere archivos externos.
AUDIO_ENABLED = True
SOUNDS = {}

def init_audio():
    global AUDIO_ENABLED, SOUNDS
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        rate = 22050
        def make_tone(f0, f1, duration, volume=0.18, kind="sine"):
            n = max(1, int(rate * duration))
            samples = array('h')
            for i in range(n):
                t = i / rate
                frac = i / max(1, n - 1)
                freq = f0 + (f1 - f0) * frac
                if kind == "noise":
                    wave = random.uniform(-1, 1) * (1 - frac)
                elif kind == "square":
                    wave = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
                else:
                    wave = math.sin(2 * math.pi * freq * t)
                fade = min(1.0, i / max(1, rate * 0.008)) * min(1.0, (n-i) / max(1, rate * 0.04))
                samples.append(int(max(-1, min(1, wave * volume * fade)) * 32767))
            return pygame.mixer.Sound(buffer=samples.tobytes())
        SOUNDS = {
            "laser": make_tone(920, 440, 0.06, 0.10),
            "heavy": make_tone(190, 65, 0.13, 0.20, "square"),
            "hit": make_tone(620, 180, 0.08, 0.13, "noise"),
            "damage": make_tone(130, 42, 0.22, 0.20, "noise"),
            "shield": make_tone(260, 1250, 0.28, 0.16),
            "upgrade": make_tone(440, 1320, 0.24, 0.15),
            "boss": make_tone(115, 35, 0.65, 0.20, "square"),
            "victory": make_tone(440, 1480, 0.48, 0.17),
            "defeat": make_tone(320, 55, 0.55, 0.18),
            "intercept": make_tone(760, 1280, 0.07, 0.10),
        }
    except (pygame.error, OSError, RuntimeError, ValueError):
        AUDIO_ENABLED = False
        SOUNDS = {}

def play_sound(name):
    if AUDIO_ENABLED and name in SOUNDS:
        try:
            SOUNDS[name].play()
        except pygame.error:
            pass

init_audio()

PLANETS = {
    "1": {"name": "La Tierra", "color": (45, 125, 235), "land": (65, 200, 115), "description": "Defiende nuestro hogar"},
    "2": {"name": "La Luna", "color": (175, 180, 195), "land": (115, 120, 140), "description": "Protege la base lunar"},
    "3": {"name": "Marte", "color": (210, 85, 55), "land": (130, 45, 35), "description": "Salva la colonia marciana"},
}

WEAPONS = {
    "Q": {"name": "Láser", "cooldown": 220, "color": CYAN, "damage": 1, "spread": 1, "speed": 10},
    "W": {"name": "Disparo pesado", "cooldown": 420, "color": YELLOW, "damage": 2, "spread": 1, "speed": 8},
    "E": {"name": "Ráfaga", "cooldown": 100, "color": (255, 125, 220), "damage": 1, "spread": 1, "speed": 11},
}

stars = [(random.randrange(WIDTH), random.randrange(HEIGHT), random.choice([1, 1, 2])) for _ in range(110)]

# La capa de nebulosas se crea una sola vez para mantener el rendimiento estable.
NEBULA_LAYER = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
pygame.draw.ellipse(NEBULA_LAYER, (45, 18, 85, 22), (-110, 88, 470, 250))
pygame.draw.ellipse(NEBULA_LAYER, (10, 65, 100, 20), (450, 272, 540, 280))
pygame.draw.ellipse(NEBULA_LAYER, (80, 20, 70, 15), (220, 440, 360, 180))


def draw_text(text, font, color, x, y, center=False):
    image = font.render(text, True, color)
    rect = image.get_rect()
    rect.center = (x, y) if center else rect.topleft
    if not center:
        rect.topleft = (x, y)
    screen.blit(image, rect)


def draw_panel(rect, fill=(8, 15, 38, 205), border=(65, 115, 175), radius=12, width=1):
    """Panel translúcido para que la interfaz se lea sin tapar el juego."""
    layer = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(layer, fill, layer.get_rect(), border_radius=radius)
    screen.blit(layer, rect.topleft)
    pygame.draw.rect(screen, border, rect, width, border_radius=radius)


def draw_glow(x, y, color, radius, rings=3):
    """Resplandor arcade ligero, sin crear superficies por cada proyectil."""
    for i in range(rings, 0, -1):
        alpha_radius = radius + i * 3
        glow_color = tuple(max(0, min(255, int(c * (0.22 if i > 1 else 0.48)))) for c in color)
        pygame.draw.circle(screen, glow_color, (int(x), int(y)), alpha_radius, 2)
    pygame.draw.circle(screen, color, (int(x), int(y)), radius)


def add_popup(game, x, y, text, color=YELLOW, life=38):
    game.setdefault("popups", []).append({"x": float(x), "y": float(y), "text": str(text),
        "color": color, "life": life, "max_life": life})

def impact_burst(game, x, y, color, amount=10, power=3.0):
    for _ in range(amount):
        angle = random.random() * math.tau
        speed = random.uniform(0.6, power)
        game["particles"].append({"x": float(x), "y": float(y),
            "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed,
            "life": random.randint(12, 27), "color": color})

def draw_popups(game):
    for popup in game.get("popups", [])[:]:
        popup["y"] -= 0.6
        popup["life"] -= 1
        ratio = max(0.0, popup["life"] / popup["max_life"])
        font = SMALL if len(popup["text"]) < 13 else pygame.font.SysFont("consolas", 14, bold=True)
        image = font.render(popup["text"], True, popup["color"])
        image.set_alpha(int(255 * min(1.0, ratio * 1.7)))
        screen.blit(image, (int(popup["x"] - image.get_width()/2), int(popup["y"])))
        if popup["life"] <= 0:
            game["popups"].remove(popup)


def draw_crosshair(pos, color=CYAN):
    x, y = pos
    pulse = 9 + int((math.sin(pygame.time.get_ticks() * 0.012) + 1) * 2)
    pygame.draw.circle(screen, color, (x, y), pulse, 1)
    pygame.draw.line(screen, color, (x - pulse - 5, y), (x - pulse + 1, y), 2)
    pygame.draw.line(screen, color, (x + pulse - 1, y), (x + pulse + 5, y), 2)
    pygame.draw.line(screen, color, (x, y - pulse - 5), (x, y - pulse + 1), 2)
    pygame.draw.line(screen, color, (x, y + pulse - 1), (x, y + pulse + 5), 2)


def draw_background():
    """Fondo espacial animado con nebulosas suaves y estrellas titilantes."""
    screen.fill(DARK)
    # Nebulosas precalculadas: el fondo no crea una superficie nueva cada fotograma.
    screen.blit(NEBULA_LAYER, (0, 0))
    ticks = pygame.time.get_ticks()
    for i, (x, y, radius) in enumerate(stars):
        twinkle = (ticks // (120 + radius * 35) + i) % 4
        color = (95 + twinkle * 15, 120 + twinkle * 12, 165 + twinkle * 18)
        yy = (y + ticks * (0.008 if radius == 1 else 0.018)) % HEIGHT
        pygame.draw.circle(screen, color, (x, int(yy)), radius)
        if radius == 2 and i % 9 == 0:
            pygame.draw.line(screen, (100, 150, 210), (x - 3, int(yy)), (x + 3, int(yy)), 1)
        if radius == 2 and i % 37 == 0:
            streak_y = int((yy + ticks * 0.035) % HEIGHT)
            pygame.draw.line(screen, (55, 100, 155), (x, streak_y - 8), (x, streak_y + 4), 1)
    # Líneas de horizonte futurista, muy tenues.
    horizon = HEIGHT - 105
    for i in range(1, 6):
        yy = horizon + i * i * 5
        pygame.draw.line(screen, (12, 35, 65), (0, yy), (WIDTH, yy), 1)
    for x in range(-WIDTH, WIDTH * 2, 90):
        pygame.draw.line(screen, (10, 27, 52), (WIDTH // 2, horizon), (x, HEIGHT), 1)


def draw_planet(planet, x, y, radius):
    pygame.draw.circle(screen, planet["color"], (x, y), radius)
    pygame.draw.circle(screen, (220, 235, 255), (x - radius // 3, y - radius // 3), radius // 5)
    # Marcas fijas para que el planeta no parpadee en cada fotograma.
    rng = random.Random(100 + int(x) + int(y))
    for _ in range(7):
        px = rng.randint(x - radius + 5, x + radius - 5)
        py = rng.randint(y - radius + 5, y + radius - 5)
        if (px - x) ** 2 + (py - y) ** 2 < (radius - 4) ** 2:
            pygame.draw.circle(screen, planet["land"], (px, py), max(2, radius // 9))


def draw_turret(x, y, target):
    dx, dy = target[0] - x, target[1] - y
    angle = math.atan2(dy, dx)
    end = (x + math.cos(angle) * 38, y + math.sin(angle) * 38)
    pygame.draw.circle(screen, (15, 25, 48), (x, y + 5), 30)
    pygame.draw.circle(screen, (45, 65, 100), (x, y), 25)
    pygame.draw.circle(screen, (20, 45, 75), (x, y), 22)
    pygame.draw.circle(screen, CYAN, (x, y), 19, 3)
    pygame.draw.line(screen, (35, 110, 145), (x + 2, y + 3), (end[0] + 2, end[1] + 3), 13)
    pygame.draw.line(screen, (80, 235, 255), (x, y), end, 9)
    pygame.draw.line(screen, WHITE, (x, y), end, 3)
    pygame.draw.circle(screen, (30, 40, 65), (x, y), 12)
    pygame.draw.circle(screen, WHITE, (x, y), 4)


def new_enemy(level):
    side = random.choice(["top", "left", "right"])
    if side == "top":
        x, y = random.randint(30, WIDTH - 30), -25
    elif side == "left":
        x, y = -25, random.randint(30, HEIGHT // 2)
    else:
        x, y = WIDTH + 25, random.randint(30, HEIGHT // 2)
    kind = random.choice(["asteroid", "asteroid", "alien", "fast"])
    speed = random.uniform(1.1, 1.9) + level * 0.13
    if kind == "fast":
        speed *= 1.55
    return {"x": float(x), "y": float(y), "kind": kind, "speed": speed,
            "size": random.randint(15, 24) if kind == "asteroid" else (13 if kind == "fast" else 19),
            "angle": random.random() * math.tau, "hp": 2 if kind == "alien" and level >= 4 else 1}


def draw_enemy(enemy):
    x, y, size = int(enemy["x"]), int(enemy["y"]), enemy["size"]
    if enemy["kind"] == "asteroid":
        points = []
        for i in range(8):
            a = i * math.tau / 8 + enemy["angle"]
            r = size * (0.78 if i % 2 else 1.0)
            points.append((x + math.cos(a) * r, y + math.sin(a) * r))
        pygame.draw.polygon(screen, (145, 115, 105), points)
        pygame.draw.polygon(screen, (220, 165, 130), points, 2)
        pygame.draw.circle(screen, (90, 75, 80), (x - 4, y + 3), max(3, size // 5))
    elif enemy["kind"] == "fast":
        points = [(x, y - size), (x + size, y + size), (x, y + size // 2), (x - size, y + size)]
        pygame.draw.polygon(screen, (255, 125, 60), points)
        pygame.draw.polygon(screen, YELLOW, points, 2)
    else:
        pygame.draw.ellipse(screen, (150, 70, 220), (x - size, y - size // 2, size * 2, size))
        pygame.draw.circle(screen, (90, 255, 160), (x - 6, y - 2), 4)
        pygame.draw.circle(screen, (90, 255, 160), (x + 6, y - 2), 4)
        pygame.draw.arc(screen, (220, 180, 255), (x - size, y - size // 2, size * 2, size), 0, math.pi, 2)


def draw_boss(elapsed, rage=0.0):
    """Dibuja un jefe arcade invulnerable; su aura crece cuanto más se enfurece."""
    x = int(WIDTH // 2 + math.sin(elapsed * 1.7) * 230)
    y = int(165 + math.sin(elapsed * 2.4) * 18)
    # Aura pulsante: pasa de violeta a rojo conforme aumenta la furia.
    pulse = 5 + int((math.sin(elapsed * (3.5 + rage * 5)) + 1) * (5 + rage * 8))
    aura_color = (int(40 + 100 * rage), 18, int(95 - 35 * rage))
    pygame.draw.ellipse(screen, aura_color, (x - 112 - pulse, y - 49 - pulse, 224 + pulse * 2, 98 + pulse * 2))
    pygame.draw.ellipse(screen, (int(90 + 120 * rage), 25, int(140 - 70 * rage)),
                        (x - 98 - pulse // 2, y - 42 - pulse // 2, 196 + pulse, 84 + pulse), 2)
    wing_color = (int(110 + 100 * rage), 35, int(105 - 45 * rage))
    pygame.draw.polygon(screen, wing_color, [(x - 48, y - 5), (x - 118, y - 42), (x - 90, y + 20), (x - 45, y + 24)])
    pygame.draw.polygon(screen, wing_color, [(x + 48, y - 5), (x + 118, y - 42), (x + 90, y + 20), (x + 45, y + 24)])
    pygame.draw.ellipse(screen, (70, 40, 130), (x - 66, y - 35, 132, 70))
    pygame.draw.ellipse(screen, (210, 80, 230), (x - 66, y - 35, 132, 70), 3)
    eye_color = (255, int(65 - 25 * rage), int(110 - 55 * rage))
    pygame.draw.circle(screen, eye_color, (x - 25, y - 3), 10 + int(rage * 3))
    pygame.draw.circle(screen, eye_color, (x + 25, y - 3), 10 + int(rage * 3))
    pygame.draw.circle(screen, WHITE, (x - 25, y - 3), 3)
    pygame.draw.circle(screen, WHITE, (x + 25, y - 3), 3)
    pygame.draw.line(screen, (255, 150, 230), (x - 23, y + 19), (x + 23, y + 19), 3)
    # Cañones laterales
    for side in (-1, 1):
        pygame.draw.circle(screen, CYAN, (x + side * 55, y + 24), 8)
        pygame.draw.circle(screen, WHITE, (x + side * 55, y + 24), 3)
    return x, y


def spawn_boss_minion(game, rage=0.0):
    """El jefe suelta refuerzos; al enfurecerse puede liberar una pareja."""
    count = 2 if rage >= 0.72 and random.random() < 0.62 else (2 if rage >= 0.38 and random.random() < 0.28 else 1)
    for _ in range(count):
        x = game.get("boss_x", WIDTH // 2) + random.randint(-75, 75)
        y = game.get("boss_y", 165) + random.randint(25, 48)
        kind = random.choice(["fast", "alien", "asteroid"])
        speed = random.uniform(1.5, 2.35) * (1 + rage * 0.32)
        game["enemies"].append({
            "x": float(max(20, min(WIDTH - 20, x))),
            "y": float(y),
            "kind": kind,
            "speed": speed,
            "size": 13 if kind == "fast" else (19 if kind == "alien" else 17),
            "angle": random.random() * math.tau,
            "hp": 1,
            "boss_minion": True,
        })


def fire_boss_volley(game, rage=0.0):
    """Dispara patrones progresivamente más densos y veloces según la furia."""
    bx, by = game.get("boss_x", WIDTH // 2), game.get("boss_y", 165)
    target_x, target_y = WIDTH // 2, HEIGHT - 58
    base_angle = math.atan2(target_y - by, target_x - bx)
    if rage >= 0.72:
        offsets = [-0.55, -0.36, -0.18, 0, 0.18, 0.36, 0.55]
    elif rage >= 0.35:
        offsets = [-0.42, -0.21, 0, 0.21, 0.42]
    else:
        offsets = [-0.16, 0, 0.16] if game.get("boss_attack_number", 0) % 2 == 0 else [-0.30, 0, 0.30]
    speed = 3.0 + rage * 2.1
    for offset in offsets:
        angle = base_angle + offset
        game["boss_shots"].append({
            "x": float(bx), "y": float(by + 25),
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed,
            "radius": 8 if rage < 0.7 else 9,
        })
    game["boss_attack_number"] = game.get("boss_attack_number", 0) + 1


def load_records():
    """Carga la tabla arcade. Si el archivo no existe o está dañado, empieza vacía."""
    try:
        with SCORE_FILE.open("r", encoding="utf-8") as file:
            records = json.load(file)
        if not isinstance(records, list):
            return []
        clean = []
        for record in records:
            if isinstance(record, dict) and isinstance(record.get("score"), int):
                clean.append({
                    "name": str(record.get("name", "PLAYER"))[:10],
                    "score": max(0, record["score"]),
                    "planet": str(record.get("planet", "La Tierra")),
                    "date": str(record.get("date", "")),
                })
        return sorted(clean, key=lambda r: r["score"], reverse=True)[:MAX_RECORDS]
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return []


def qualifies_for_record(score):
    records = load_records()
    return len(records) < MAX_RECORDS or score > records[-1]["score"]


def save_record(name, score, planet):
    records = load_records()
    records.append({
        "name": (name.strip() or "PLAYER")[:10].upper(),
        "score": int(score),
        "planet": planet,
        "date": datetime.now().strftime("%d/%m/%Y"),
    })
    records.sort(key=lambda r: r["score"], reverse=True)
    records = records[:MAX_RECORDS]
    try:
        with SCORE_FILE.open("w", encoding="utf-8") as file:
            json.dump(records, file, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def reset_game(planet_key):
    return {
        "planet": PLANETS[planet_key],
        "health": 100,
        "score": 0,
        "combo": 0,
        "combo_timer": 0.0,
        "best_combo": 0,
        "kills": 0,
        "damage_taken": 0,
        "level": 1,
        "enemies": [],
        "shots": [],
        "particles": [],
        "spawn_timer": 0,
        "shot_timer": 0,
        "elapsed": 0,
        "boss_active": False,
        "boss_x": WIDTH // 2,
        "boss_y": 165,
        "boss_hits": 0,
        "boss_defeated": False,
        "boss_shots": [],
        "boss_attack_timer": 0,
        "boss_minion_timer": 0,
        "boss_attack_number": 0,
        "boss_rage": 0.0,
        "weapon": "Q",
        "game_over": False,
        "auto_fire": False,
        "triple_shot": False,
        "damage_bonus": 0,
        "cooldown_factor": 1.0,
        "speed_bonus": 0,
        "pierce_bonus": 0,
        "upgrades": [],
        "upgrade_options": [],
        "pending_level": 1,
        "next_level_score": 200,
        "shield_timer": 0.0,
        "shield_cooldown": 0.0,
        "shield_uses": 0,
        "final_phase_started": False,
        "damage_flash": 0.0,
        "popups": [],
        "boss_intro_timer": 0.0,
        "boss_intro_seen": False,
        "shots_fired": 0,
        "shots_hit": 0,
    }


UPGRADES = [
    {"id": "triple", "name": "Disparo triple", "description": "Cada disparo lanza 3 proyectiles.", "color": YELLOW},
    {"id": "auto", "name": "Tiro automático", "description": "La torreta dispara sola hacia el cursor.", "color": GREEN},
    {"id": "rapid", "name": "Cañón acelerado", "description": "Dispara un 30% más rápido.", "color": (255, 125, 220)},
    {"id": "damage", "name": "Láser reforzado", "description": "Cada proyectil hace +1 de daño.", "color": RED},
    {"id": "speed", "name": "Proyectil veloz", "description": "Los proyectiles viajan más rápido.", "color": CYAN},
    {"id": "pierce", "name": "Núcleo perforante", "description": "Los proyectiles atraviesan un enemigo extra.", "color": (180, 130, 255)},
]


def make_upgrade_options(game):
    # Evita ofrecer de nuevo las mejoras únicas; las mejoras de estadísticas pueden repetirse.
    repeatable = {"rapid", "damage", "speed"}
    available = [u for u in UPGRADES if u["id"] not in game["upgrades"] or u["id"] in repeatable]
    return random.sample(available, min(3, len(available)))


def apply_upgrade(game, upgrade):
    uid = upgrade["id"]
    if uid == "triple":
        game["triple_shot"] = True
    elif uid == "auto":
        game["auto_fire"] = True
    elif uid == "rapid":
        game["cooldown_factor"] = max(0.35, game["cooldown_factor"] * 0.70)
    elif uid == "damage":
        game["damage_bonus"] += 1
    elif uid == "speed":
        game["speed_bonus"] += 3
    elif uid == "pierce":
        game["pierce_bonus"] += 1
    game["upgrades"].append(uid)


def fire_weapon(game, target):
    weapon = WEAPONS[game["weapon"]]
    turret_x, turret_y = WIDTH // 2, HEIGHT - 75
    dx, dy = target[0] - turret_x, target[1] - turret_y
    base_angle = math.atan2(dy, dx)
    angles = [base_angle]
    if game["triple_shot"]:
        angles = [base_angle - 0.18, base_angle, base_angle + 0.18]
    play_sound("heavy" if game["weapon"] == "W" else "laser")
    for angle in angles:
        game["shots_fired"] = game.get("shots_fired", 0) + 1
        game["shots"].append({
            "x": float(turret_x), "y": float(turret_y),
            "vx": math.cos(angle) * (weapon["speed"] + game["speed_bonus"]),
            "vy": math.sin(angle) * (weapon["speed"] + game["speed_bonus"]),
            "color": weapon["color"],
            "damage": weapon["damage"] + game["damage_bonus"],
            "pierce": game["pierce_bonus"],
        })


def health_color(health):
    if health > 60:
        return GREEN
    if health > 30:
        return YELLOW
    return RED


def main():
    global AUDIO_ENABLED
    state = "menu"
    game = None
    running = True
    mouse_pos = (WIDTH // 2, HEIGHT // 2)
    record_name = ""
    record_message = ""

    while running:
        dt = clock.tick(60)
        draw_background()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_m:
                    AUDIO_ENABLED = not AUDIO_ENABLED
                    if not AUDIO_ENABLED:
                        try:
                            pygame.mixer.stop()
                        except pygame.error:
                            pass
                if state == "menu" and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    game = reset_game(str(event.key - pygame.K_0))
                    state = "playing"
                elif state == "upgrade" and game and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    index = event.key - pygame.K_1
                    if index < len(game["upgrade_options"]):
                        apply_upgrade(game, game["upgrade_options"][index])
                        play_sound("upgrade")
                        add_popup(game, WIDTH // 2, 170, "MEJORA INSTALADA", GREEN, 42)
                        game["level"] = game["pending_level"]
                        game["next_level_score"] += 200 + game["level"] * 75
                        game["upgrade_options"] = []
                        state = "playing"
                elif state == "menu" and event.key == pygame.K_h:
                    state = "leaderboard"
                elif state == "leaderboard" and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    state = "menu"
                elif state == "record_entry" and game:
                    if event.key == pygame.K_RETURN:
                        if save_record(record_name, game["score"], game["planet"]["name"]):
                            record_message = "¡Récord guardado!"
                        else:
                            record_message = "No se pudo guardar el archivo de récords."
                        state = game["end_state"]
                    elif event.key == pygame.K_BACKSPACE:
                        record_name = record_name[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        state = game["end_state"]
                    elif event.unicode and event.unicode.isprintable() and event.unicode not in "\t\n\r" and len(record_name) < 10:
                        if event.unicode.isalnum() or event.unicode == " ":
                            record_name += event.unicode.upper()
                elif state in ("gameover", "victory") and event.key == pygame.K_RETURN:
                    state = "menu"
                elif state in ("gameover", "victory") and event.key == pygame.K_r and game:
                    game = reset_game(next(key for key, value in PLANETS.items() if value["name"] == game["planet"]["name"]))
                    state = "playing"
                elif event.key == pygame.K_ESCAPE:
                    if state in ("playing", "paused"):
                        state = "menu"
                    else:
                        running = False
                elif state == "playing":
                    if event.key == pygame.K_p:
                        state = "paused"
                    elif event.key == pygame.K_f and game and game["shield_cooldown"] <= 0:
                        # Escudo de emergencia: protege el planeta durante un instante.
                        game["shield_timer"] = 1.8
                        game["shield_cooldown"] = 12.0
                        game["shield_uses"] += 1
                        play_sound("shield")
                        add_popup(game, WIDTH // 2, HEIGHT - 105, "ESCUDO ACTIVADO", CYAN, 38)
                        impact_burst(game, WIDTH // 2, HEIGHT - 30, CYAN, 20, 4.0)
                        for _ in range(18):
                            game["particles"].append({"x": WIDTH // 2 + random.randint(-70, 70),
                                                      "y": HEIGHT - 25 + random.randint(-8, 8),
                                                      "vx": random.uniform(-2.8, 2.8),
                                                      "vy": random.uniform(-2.5, 0.5), "life": 22})
                    elif event.key == pygame.K_q:
                        game["weapon"] = "Q"
                    elif event.key == pygame.K_w:
                        game["weapon"] = "W"
                    elif event.key == pygame.K_e:
                        game["weapon"] = "E"
                elif state == "paused" and event.key in (pygame.K_p, pygame.K_SPACE):
                    state = "playing"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos
                if state == "upgrade" and game:
                    for i, upgrade in enumerate(game["upgrade_options"]):
                        card = pygame.Rect(70, 190 + i * 125, WIDTH - 140, 105)
                        if card.collidepoint(event.pos):
                            apply_upgrade(game, upgrade)
                            play_sound("upgrade")
                            add_popup(game, WIDTH // 2, 170, "MEJORA INSTALADA", GREEN, 42)
                            game["level"] = game["pending_level"]
                            game["next_level_score"] += 200 + game["level"] * 75
                            game["upgrade_options"] = []
                            state = "playing"
                            break
                elif state == "playing" and game and not game["game_over"]:
                    fire_weapon(game, event.pos)

        mouse_pos = pygame.mouse.get_pos()

        if state == "menu":
            draw_text("DEFENSA PLANETARIA", BIG, CYAN, WIDTH // 2, 90, True)
            draw_text("Elegí qué planeta querés proteger", FONT, WHITE, WIDTH // 2, 150, True)
            for key, planet in PLANETS.items():
                y = 245 + (int(key) - 1) * 105
                draw_planet(planet, 230, y, 34)
                draw_text(f"{key}  -  {planet['name']}", FONT, WHITE, 300, y - 18)
                draw_text(planet["description"], SMALL, (170, 190, 220), 300, y + 12)
            draw_text("1 / 2 / 3: elegir planeta", SMALL, YELLOW, WIDTH // 2, 560, True)
            draw_text("H: tabla de récords     M: sonido     ESC: salir", SMALL, WHITE, WIDTH // 2, 592, True)
            draw_text("Sobreviví, conseguí puntos y entrá en el TOP 10", SMALL, CYAN, WIDTH // 2, 622, True)
            draw_text("F: escudo de emergencia  |  ESPACIO: fuego continuo  |  Clic: disparo", SMALL, (150, 225, 255), WIDTH // 2, 530, True)

        elif state == "leaderboard":
            draw_text("TABLA DE RÉCORDS", BIG, YELLOW, WIDTH // 2, 75, True)
            draw_text("TOP 10 - DEFENSA PLANETARIA", SMALL, CYAN, WIDTH // 2, 120, True)
            records = load_records()
            if not records:
                draw_text("Todavía no hay puntuaciones. ¡Sé el primero!", FONT, WHITE, WIDTH // 2, 280, True)
            else:
                draw_text("#     JUGADOR       PUNTOS       PLANETA       FECHA", SMALL, (150, 180, 220), 115, 160)
                for i, record in enumerate(records):
                    y = 198 + i * 34
                    color = YELLOW if i == 0 else (CYAN if i < 3 else WHITE)
                    draw_text(f"{i + 1:>2}    {record['name']:<10}   {record['score']:>7}", SMALL, color, 115, y)
                    draw_text(record['planet'][:12], SMALL, (170, 195, 220), 475, y)
                    draw_text(record['date'][:10], SMALL, (140, 160, 190), 650, y)
            draw_text("ENTER / ESC: volver al menú", SMALL, WHITE, WIDTH // 2, 605, True)

        elif state == "upgrade" and game:
            draw_text("¡NUEVO NIVEL!", BIG, CYAN, WIDTH // 2, 75, True)
            draw_text(f"Elegí una mejora para la torreta - Nivel {game['pending_level']}",
                      SMALL, WHITE, WIDTH // 2, 125, True)
            for i, upgrade in enumerate(game["upgrade_options"]):
                y = 190 + i * 125
                card = pygame.Rect(70, y, WIDTH - 140, 105)
                hovered = card.collidepoint(mouse_pos)
                pygame.draw.rect(screen, (28, 42, 75) if hovered else (16, 25, 52), card, border_radius=12)
                pygame.draw.rect(screen, upgrade["color"], card, width=3, border_radius=12)
                draw_text(f"{i + 1}. {upgrade['name']}", FONT, upgrade["color"], 95, y + 16)
                draw_text(upgrade["description"], SMALL, WHITE, 95, y + 57)
            draw_text("Elegí con 1, 2 o 3, o hacé clic en una tarjeta", SMALL,
                      (170, 195, 220), WIDTH // 2, 590, True)

        elif state in ("playing", "paused", "record_entry", "gameover", "victory") and game:
            planet = game["planet"]
            draw_planet(planet, WIDTH // 2, HEIGHT + 92, 185)
            if state == "playing":
                draw_crosshair(mouse_pos, (255, 125, 220) if game["weapon"] == "E" else CYAN)
            pygame.draw.rect(screen, (30, 55, 85), (WIDTH // 2 - 85, HEIGHT - 48, 170, 12), border_radius=6)
            draw_turret(WIDTH // 2, HEIGHT - 75, mouse_pos)
            if game["shield_timer"] > 0:
                shield_pulse = 48 + int(4 * math.sin(pygame.time.get_ticks() * 0.025))
                pygame.draw.circle(screen, (45, 220, 255), (WIDTH // 2, HEIGHT - 30), shield_pulse, 4)
                pygame.draw.circle(screen, (130, 245, 255), (WIDTH // 2, HEIGHT - 30), shield_pulse - 7, 1)

            if not game["game_over"] and state == "playing":
                game["elapsed"] += dt / 1000
                game["spawn_timer"] += dt
                game["shot_timer"] += dt
                game["combo_timer"] = max(0.0, game["combo_timer"] - dt / 1000)
                if game["combo_timer"] <= 0:
                    game["combo"] = 0
                game["damage_flash"] = max(0.0, game["damage_flash"] - dt / 1000)
                game["shield_timer"] = max(0.0, game["shield_timer"] - dt / 1000)
                game["shield_cooldown"] = max(0.0, game["shield_cooldown"] - dt / 1000)
                # Últimos 10 segundos: clímax visual y ataques más rápidos.
                if game["elapsed"] >= GAME_DURATION - 10 and not game["final_phase_started"]:
                    game["final_phase_started"] = True
                    game["particles"].extend({"x": random.randint(0, WIDTH), "y": random.randint(0, HEIGHT // 2),
                                              "vx": random.uniform(-1.5, 1.5), "vy": random.uniform(1.0, 3.5),
                                              "life": random.randint(15, 28)} for _ in range(45))
                # El jefe entra al comenzar los últimos 30 segundos. La fase se centra en él.
                if game["elapsed"] >= BOSS_START and not game["boss_active"]:
                    game["boss_active"] = True
                    game["enemies"].clear()
                    game["shots"].clear()
                    game["boss_shots"].clear()
                    game["spawn_timer"] = 0
                    game["boss_attack_timer"] = 0
                    game["boss_minion_timer"] = 0
                    game["boss_rage"] = 0.0
                    game["boss_intro_timer"] = 2.5
                    game["boss_intro_seen"] = True
                    play_sound("boss")
                    add_popup(game, WIDTH // 2, 380, "JEFE FINAL DETECTADO", (255, 100, 210), 60)
                if game["boss_intro_timer"] > 0:
                    game["boss_intro_timer"] = max(0.0, game["boss_intro_timer"] - dt / 1000)
                if game["score"] >= game["next_level_score"] and not game["boss_active"]:
                    game["pending_level"] = game["level"] + 1
                    game["upgrade_options"] = make_upgrade_options(game)
                    state = "upgrade"
                if not game["boss_active"]:
                    spawn_delay = max(280, 1000 - game["level"] * 60)
                    if game["spawn_timer"] >= spawn_delay:
                        game["enemies"].append(new_enemy(game["level"]))
                        game["spawn_timer"] = 0
                else:
                    # La furia crece linealmente durante los 30 segundos del jefe.
                    rage = max(0.0, min(1.0, (game["elapsed"] - BOSS_START) / BOSS_DURATION))
                    game["boss_rage"] = rage
                    game["boss_attack_timer"] += dt
                    game["boss_minion_timer"] += dt
                    final_surge = 260 if game["elapsed"] >= GAME_DURATION - 10 else 0
                    attack_interval = max(330, int(1450 - rage * 880 - final_surge))
                    minion_interval = max(700, int(3200 - rage * 2050 - (220 if final_surge else 0)))
                    enemy_limit = min(12, 7 + int(rage * 5))
                    if game["boss_attack_timer"] >= attack_interval:
                        fire_boss_volley(game, rage)
                        game["boss_attack_timer"] = 0
                    if game["boss_minion_timer"] >= minion_interval and len(game["enemies"]) < enemy_limit:
                        spawn_boss_minion(game, rage)
                        game["boss_minion_timer"] = 0

                # Mantener ESPACIO apretado dispara continuamente.
                keys = pygame.key.get_pressed()
                effective_cooldown = max(45, int(WEAPONS[game["weapon"]]["cooldown"] * game["cooldown_factor"]))
                if (keys[pygame.K_SPACE] or game["auto_fire"]) and game["shot_timer"] >= effective_cooldown:
                    fire_weapon(game, mouse_pos)
                    game["shot_timer"] = 0

                if game["elapsed"] >= GAME_DURATION and game["health"] > 0:
                    game["boss_defeated"] = True
                    play_sound("victory")
                    impact_burst(game, WIDTH // 2, 165, (255, 140, 230), 70, 7.0)
                    game["boss_shots"].clear()
                    game["enemies"].clear()
                    game["end_state"] = "victory"
                    if qualifies_for_record(game["score"]):
                        record_name = ""
                        record_message = ""
                        state = "record_entry"
                    else:
                        state = "victory"

            # Jefe: no tiene vida ni puede ser eliminado por disparos; cada impacto da puntos.
            if game["boss_active"]:
                boss_rage = max(0.0, min(1.0, (game["elapsed"] - BOSS_START) / BOSS_DURATION))
                game["boss_x"], game["boss_y"] = draw_boss(game["elapsed"], boss_rage)
                boss_remaining = max(0, math.ceil(GAME_DURATION - game["elapsed"]))
                pygame.draw.rect(screen, (35, 25, 55), (WIDTH // 2 - 170, 235, 340, 14), border_radius=7)
                pygame.draw.rect(screen, (220, 65, 180), (WIDTH // 2 - 170, 235, int(340 * boss_remaining / BOSS_DURATION), 14), border_radius=7)
                pygame.draw.rect(screen, (255, 140, 230), (WIDTH // 2 - 170, 235, 340, 14), 2, border_radius=7)
                rage_color = (255, int(180 - 110 * boss_rage), int(90 - 35 * boss_rage))
                pygame.draw.rect(screen, (35, 20, 45), (WIDTH // 2 - 170, 256, 340, 12), border_radius=6)
                pygame.draw.rect(screen, rage_color, (WIDTH // 2 - 170, 256, int(340 * boss_rage), 12), border_radius=6)
                pygame.draw.rect(screen, (255, 170, 220), (WIDTH // 2 - 170, 256, 340, 12), 1, border_radius=6)
                draw_text(f"JEFE FINAL  -  {boss_remaining}s", FONT, (255, 130, 230), WIDTH // 2, 286, True)
                rage_label = "FURIA: CRÍTICA" if boss_rage >= 0.72 else ("FURIA: ALTA" if boss_rage >= 0.35 else "FURIA: CRECIENDO")
                draw_text(rage_label, SMALL, rage_color, WIDTH // 2, 311, True)
                draw_text("¡Disparale para sumar puntos y esquivá sus ataques!", SMALL, WHITE, WIDTH // 2, 333, True)
                if boss_remaining <= 10:
                    # Borde de alarma pulsante durante la última fase.
                    alarm = (pygame.time.get_ticks() // 100) % 2 == 0
                    if alarm:
                        pygame.draw.rect(screen, (255, 45, 65), (3, 3, WIDTH - 6, HEIGHT - 6), 4, border_radius=12)
                    draw_text("¡SOBRECARGA! ¡AGUANTÁ 10 SEGUNDOS!", SMALL, (255, 95, 105), WIDTH // 2, 356, True)

            # Proyectiles del jefe: se pueden destruir disparándoles o dejarán daño al planeta.
            for boss_shot in game["boss_shots"][:]:
                if state == "playing" and not game["game_over"]:
                    boss_shot["x"] += boss_shot["vx"]
                    boss_shot["y"] += boss_shot["vy"]
                bx, by = int(boss_shot["x"]), int(boss_shot["y"])
                draw_glow(bx, by, (255, 85, 175), boss_shot["radius"], 3)
                pygame.draw.circle(screen, (255, 210, 240), (bx - 2, by - 2), 3)
                if state == "playing" and by >= HEIGHT - 58:
                    if boss_shot in game["boss_shots"]:
                        game["boss_shots"].remove(boss_shot)
                    if game["shield_timer"] > 0:
                        game["score"] += 5
                        for _ in range(6):
                            game["particles"].append({"x": bx, "y": by, "vx": random.uniform(-2.5, 2.5),
                                                      "vy": random.uniform(-2.5, 0), "life": 18})
                        continue
                    game["health"] = max(0, game["health"] - 6)
                    game["damage_taken"] += 6
                    game["damage_flash"] = 0.35
                    play_sound("damage")
                    add_popup(game, WIDTH // 2, HEIGHT - 115, "-6 VIDA", RED, 28)
                    for _ in range(5):
                        game["particles"].append({"x": bx, "y": by, "vx": random.uniform(-2, 2),
                                                  "vy": random.uniform(-2, 1), "life": 16})
                    if game["health"] <= 0:
                        game["game_over"] = True
                        play_sound("defeat")
                        game["end_state"] = "gameover"
                        if qualifies_for_record(game["score"]):
                            record_name = ""
                            record_message = ""
                            state = "record_entry"
                        else:
                            state = "gameover"
                elif bx < -30 or bx > WIDTH + 30 or by < -30 or by > HEIGHT + 30:
                    if boss_shot in game["boss_shots"]:
                        game["boss_shots"].remove(boss_shot)

            # Enemigos
            for enemy in game["enemies"][:]:
                dx = WIDTH // 2 - enemy["x"]
                dy = HEIGHT - 20 - enemy["y"]
                length = max(1, math.hypot(dx, dy))
                if not game["game_over"] and state == "playing":
                    enemy["x"] += dx / length * enemy["speed"]
                    enemy["y"] += dy / length * enemy["speed"]
                    enemy["angle"] += 0.025
                draw_enemy(enemy)
                if state == "playing" and (enemy["y"] > HEIGHT - 42 or enemy["x"] < -40 or enemy["x"] > WIDTH + 40):
                    game["enemies"].remove(enemy)
                    if game["shield_timer"] > 0:
                        game["score"] += 8
                        for _ in range(6):
                            game["particles"].append({"x": WIDTH // 2 + random.randint(-35, 35),
                                                      "y": HEIGHT - 35, "vx": random.uniform(-2, 2),
                                                      "vy": random.uniform(-3, 0), "life": 16})
                        continue
                    damage = 12 if enemy["kind"] == "alien" else 8
                    game["health"] = max(0, game["health"] - damage)
                    game["damage_taken"] += damage
                    game["damage_flash"] = 0.35
                    play_sound("damage")
                    add_popup(game, WIDTH // 2, HEIGHT - 115, f"-{damage} VIDA", RED, 28)
                    if game["health"] <= 0:
                        game["health"] = 0
                        game["game_over"] = True
                        play_sound("defeat")
                        game["end_state"] = "gameover"
                        if qualifies_for_record(game["score"]):
                            record_name = ""
                            record_message = ""
                            state = "record_entry"
                        else:
                            state = "gameover"

            # Disparos y colisiones
            for shot in game["shots"][:]:
                if state == "playing" and not game["game_over"]:
                    shot["x"] += shot["vx"]
                    shot["y"] += shot["vy"]
                draw_glow(shot["x"], shot["y"], shot["color"], 4, 2)
                pygame.draw.circle(screen, WHITE, (int(shot["x"]), int(shot["y"])), 2)
                if not (-20 <= shot["x"] <= WIDTH + 20 and -20 <= shot["y"] <= HEIGHT + 20):
                    game["shots"].remove(shot)
                    continue
                if state == "playing" and not game["game_over"]:
                    # La torreta puede interceptar las salvas del jefe para proteger el planeta.
                    intercepted = None
                    for boss_shot in game["boss_shots"]:
                        if math.hypot(shot["x"] - boss_shot["x"], shot["y"] - boss_shot["y"]) < boss_shot["radius"] + 6:
                            intercepted = boss_shot
                            break
                    if intercepted:
                        if intercepted in game["boss_shots"]:
                            game["boss_shots"].remove(intercepted)
                        game["score"] += 3
                        play_sound("intercept")
                        add_popup(game, intercepted["x"], intercepted["y"], "+3 INTERCEPTADO", CYAN, 24)
                        impact_burst(game, intercepted["x"], intercepted["y"], CYAN, 8, 2.5)
                        for _ in range(4):
                            game["particles"].append({"x": intercepted["x"], "y": intercepted["y"],
                                                      "vx": random.uniform(-2, 2), "vy": random.uniform(-2, 2), "life": 12})
                        if shot in game["shots"]:
                            game["shots"].remove(shot)
                        continue
                    # El jefe es invulnerable: los impactos dan puntos, pero nunca reducen su duración.
                    if game["boss_active"] and abs(shot["x"] - game["boss_x"]) < 72 and abs(shot["y"] - game["boss_y"]) < 42:
                        game["score"] += 5
                        game["shots_hit"] = game.get("shots_hit", 0) + 1
                        add_popup(game, shot["x"], shot["y"], "+5 JEFE", (255, 135, 220), 24)
                        impact_burst(game, shot["x"], shot["y"], (255, 100, 220), 7, 2.5)
                        for _ in range(3):
                            game["particles"].append({"x": shot["x"], "y": shot["y"],
                                                      "vx": random.uniform(-2, 2), "vy": random.uniform(-2, 2), "life": 12})
                        if shot in game["shots"]:
                            game["shots"].remove(shot)
                        continue
                    hit = None
                    for enemy in game["enemies"]:
                        if math.hypot(shot["x"] - enemy["x"], shot["y"] - enemy["y"]) < enemy["size"] + 6:
                            hit = enemy
                            break
                    if hit:
                        hit["hp"] -= shot.get("damage", WEAPONS[game["weapon"]]["damage"])
                        if hit["hp"] <= 0:
                            if hit in game["enemies"]:
                                game["enemies"].remove(hit)
                            base_points = 20 if hit["kind"] == "alien" else (15 if hit["kind"] == "fast" else 10)
                            game["combo"] = min(10, game["combo"] + 1) if game["combo_timer"] > 0 else 1
                            game["best_combo"] = max(game["best_combo"], game["combo"])
                            game["combo_timer"] = 2.2
                            multiplier = 1 + min(4, (game["combo"] - 1) // 3)
                            game["score"] += base_points * multiplier
                            game["kills"] += 1
                            game["shots_hit"] = game.get("shots_hit", 0) + 1
                            play_sound("hit")
                            add_popup(game, hit["x"], hit["y"] - hit["size"], f"+{base_points * multiplier}", YELLOW)
                            impact_burst(game, hit["x"], hit["y"], (255, 165, 95) if hit["kind"] == "asteroid" else (190, 100, 255), 12, 3.5)
                            for _ in range(8):
                                game["particles"].append({"x": hit["x"], "y": hit["y"],
                                                          "vx": random.uniform(-2.5, 2.5),
                                                          "vy": random.uniform(-2.5, 2.5), "life": 18})
                        if shot.get("pierce", 0) > 0:
                            shot["pierce"] -= 1
                        elif shot in game["shots"]:
                            game["shots"].remove(shot)

            for particle in game["particles"][:]:
                particle["x"] += particle["vx"]
                particle["y"] += particle["vy"]
                particle["life"] -= 1
                particle_color = particle.get("color", (255, 180 + (particle["life"] % 70), 90))
                pygame.draw.circle(screen, particle_color, (int(particle["x"]), int(particle["y"])), max(1, min(4, particle["life"] // 5)))
                if particle["life"] <= 0:
                    game["particles"].remove(particle)

            draw_popups(game)
            if game.get("boss_intro_timer", 0) > 0 and state == "playing":
                intro_alpha = min(190, int(190 * min(1.0, game["boss_intro_timer"] * 1.7)))
                intro = pygame.Surface((WIDTH, 78), pygame.SRCALPHA)
                intro.fill((48, 4, 38, intro_alpha))
                screen.blit(intro, (0, 370))
                pygame.draw.line(screen, (255, 65, 175), (0, 370), (WIDTH, 370), 2)
                pygame.draw.line(screen, (255, 65, 175), (0, 448), (WIDTH, 448), 2)
                draw_text("JEFE FINAL DETECTADO", FONT, (255, 105, 210), WIDTH // 2, 392, True)
                draw_text("PROTOCOLO DE SOBRECARGA INICIADO", SMALL, WHITE, WIDTH // 2, 422, True)

            # Interfaz con paneles legibles estilo consola espacial.
            draw_panel(pygame.Rect(10, 8, 205, 118), fill=(5, 12, 32, 205), border=(35, 95, 145), radius=10)
            draw_panel(pygame.Rect(WIDTH - 225, 8, 215, 96), fill=(5, 12, 32, 205), border=(35, 95, 145), radius=10)
            draw_text(planet["name"], FONT, WHITE, 20, 18)
            draw_text(f"Puntos: {game['score']}", FONT, YELLOW, 20, 50)
            draw_text(f"Nivel: {game['level']}", FONT, CYAN, 20, 82)
            if game["combo"] >= 2 and game["combo_timer"] > 0:
                combo_color = YELLOW if game["combo"] >= 6 else (255, 150, 220)
                draw_text(f"COMBO x{1 + min(4, (game['combo'] - 1) // 3)}  ({game['combo']})", SMALL, combo_color, 20, 112)
            remaining = max(0, math.ceil(GAME_DURATION - game["elapsed"]))
            if game["boss_active"]:
                draw_text(f"JEFE: {remaining}s", FONT, (255, 130, 230), WIDTH // 2, 55, True)
            else:
                draw_text(f"Tiempo: {remaining // 60}:{remaining % 60:02d}", FONT, WHITE, WIDTH // 2, 55, True)
            draw_text("VIDA DEL PLANETA", SMALL, WHITE, WIDTH - 210, 18)
            pygame.draw.rect(screen, (65, 35, 50), (WIDTH - 210, 43, 180, 20), border_radius=5)
            pygame.draw.rect(screen, health_color(game["health"]),
                             (WIDTH - 210, 43, int(180 * game["health"] / 100), 20), border_radius=5)
            draw_text(f"{game['health']}%", SMALL, WHITE, WIDTH - 210, 68)

            current = game["weapon"]
            draw_text("ARMAS (Q / W / E):", SMALL, WHITE, 20, 125)
            labels = [("Q", "Láser", CYAN), ("W", "Pesado", YELLOW), ("E", "Ráfaga", (255, 125, 220))]
            for i, (key, label, color) in enumerate(labels):
                x = 20 + i * 145
                selected = current == key
                pygame.draw.rect(screen, color if selected else (55, 65, 90), (x, 151, 130, 32), border_radius=6, width=2)
                draw_text(f"{key}: {label}", SMALL, color if selected else WHITE, x + 8, 158)
            firing_hint = "¡INTERCEPTÁ LAS SALVAS ROSAS!" if game["boss_active"] else ("TIRO AUTOMÁTICO ACTIVADO" if game["auto_fire"] else "ESPACIO / clic: disparar  |  P: pausa")
            draw_text(firing_hint, SMALL, (170, 195, 220), WIDTH // 2, HEIGHT - 18, True)
            draw_text("AUDIO ON [M]" if AUDIO_ENABLED else "AUDIO OFF [M]", SMALL,
                      (100, 230, 180) if AUDIO_ENABLED else (145, 150, 170), WIDTH - 150, HEIGHT - 42)
            shield_text = "ESCUDO ACTIVO" if game["shield_timer"] > 0 else (f"ESCUDO: {game['shield_cooldown']:.1f}s" if game["shield_cooldown"] > 0 else "ESCUDO LISTO [F]")
            shield_color = CYAN if game["shield_timer"] > 0 or game["shield_cooldown"] <= 0 else (155, 165, 190)
            draw_text(shield_text, SMALL, shield_color, WIDTH - 205, 112)
            if game["upgrades"]:
                names = {u["id"]: u["name"] for u in UPGRADES}
                active = list(dict.fromkeys(names[uid] for uid in game["upgrades"]))
                draw_text("Mejoras: " + ", ".join(active[:3]), SMALL, (190, 210, 245), 20, 190)
                if len(active) > 3:
                    draw_text("+ más mejoras", SMALL, (190, 210, 245), 20, 210)

            if state == "paused":
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 15, 190))
                screen.blit(overlay, (0, 0))
                draw_text("PAUSA", BIG, CYAN, WIDTH // 2, HEIGHT // 2 - 25, True)
                draw_text("P o ESPACIO: continuar   |   ESC: menú   |   M: sonido", SMALL, WHITE, WIDTH // 2, HEIGHT // 2 + 30, True)

            if state == "record_entry":
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 15, 205))
                screen.blit(overlay, (0, 0))
                draw_text("¡NUEVO RÉCORD!", BIG, YELLOW, WIDTH // 2, HEIGHT // 2 - 100, True)
                draw_text(f"Puntuación: {game['score']}", FONT, WHITE, WIDTH // 2, HEIGHT // 2 - 48, True)
                pygame.draw.rect(screen, (18, 32, 62), (WIDTH // 2 - 180, HEIGHT // 2 - 15, 360, 54), border_radius=8)
                pygame.draw.rect(screen, CYAN, (WIDTH // 2 - 180, HEIGHT // 2 - 15, 360, 54), 2, border_radius=8)
                shown_name = record_name + ("_" if pygame.time.get_ticks() % 1000 < 500 else " ")
                draw_text(shown_name or "_", FONT, YELLOW, WIDTH // 2, HEIGHT // 2 + 12, True)
                draw_text("Escribí tus iniciales o nombre (máx. 10 caracteres)", SMALL, WHITE, WIDTH // 2, HEIGHT // 2 + 62, True)
                draw_text("ENTER: guardar récord   |   ESC: omitir", SMALL, (170, 195, 220), WIDTH // 2, HEIGHT // 2 + 96, True)

            if state in ("gameover", "victory"):
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 15, 190))
                screen.blit(overlay, (0, 0))
                if state == "victory":
                    draw_text("¡PLANETA SALVADO!", BIG, GREEN, WIDTH // 2, HEIGHT // 2 - 55, True)
                    draw_text("¡Resististe la fase final de 30 segundos!", FONT, WHITE, WIDTH // 2, HEIGHT // 2, True)
                else:
                    draw_text("PLANETA PERDIDO", BIG, RED, WIDTH // 2, HEIGHT // 2 - 55, True)
                    draw_text("Las defensas no resistieron la invasión.", FONT, WHITE, WIDTH // 2, HEIGHT // 2, True)
                draw_text(f"Puntuación final: {game['score']}", FONT, YELLOW, WIDTH // 2, HEIGHT // 2 + 42, True)
                draw_text(f"Bajas: {game['kills']}  |  Mejor combo: x{game['best_combo']}  |  Escudos: {game['shield_uses']}", SMALL, (175, 215, 245), WIDTH // 2, HEIGHT // 2 + 72, True)
                accuracy = int(100 * game.get("shots_hit", 0) / max(1, game.get("shots_fired", 0)))
                draw_text(f"Precisión aprox.: {accuracy}%  |  Disparos: {game.get('shots_fired', 0)}", SMALL, (155, 190, 225), WIDTH // 2, HEIGHT // 2 + 96, True)
                if record_message:
                    draw_text(record_message, SMALL, CYAN, WIDTH // 2, HEIGHT // 2 + 98, True)
                draw_text("R: jugar de nuevo   |   ENTER: menú   |   ESC: salir", SMALL, WHITE, WIDTH // 2, HEIGHT // 2 + 140, True)

        # Destello rojo al recibir daño: feedback inmediato sin sacudir la ventana.
        if game and game.get("damage_flash", 0) > 0 and state in ("playing", "paused"):
            alpha = int(105 * min(1.0, game["damage_flash"] / 0.35))
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.rect(flash, (255, 25, 55, alpha), (0, 0, WIDTH, HEIGHT), 9)
            screen.blit(flash, (0, 0))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()

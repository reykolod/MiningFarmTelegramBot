import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from config import BITCOIN_EXCHANGE_RATE as _ECONOMY_ANCHOR_RATE
from exchange_rate import get_bitcoin_exchange_rate


@dataclass
class ShopItem:
    id: str
    name: str
    price: float
    description: str
    item_type: str                                                                    
    effects: Dict[str, float]                                                                                           
                
    gpu_slots: int = 0                                                
    asic_slots: int = 0                                         


PRICE_ROUND_STEP_USD: int = 50

ECONOMY_PRICE_EXPONENT: float = 0.5
ECONOMY_PRICE_MULTIPLIER_MIN: float = 0.6
ECONOMY_PRICE_MULTIPLIER_MAX: float = 2.0


def _round_up_to_step(value: float, step: int) -> int:
    v = float(value or 0)
    s = int(step or 1)
    if s <= 0:
        s = 1
    if v <= 0:
        return s
    return int(math.ceil(v / float(s)) * float(s))


def _get_price_multiplier(*, rate_usd_per_btc: Optional[float] = None) -> float:
    anchor = float(_ECONOMY_ANCHOR_RATE or 1)
    if anchor <= 0:
        anchor = 1.0
    rate = float(rate_usd_per_btc) if rate_usd_per_btc is not None else float(get_bitcoin_exchange_rate() or 0)
    if rate <= 0:
        rate = anchor
    raw = float(rate / anchor)
    exp = float(ECONOMY_PRICE_EXPONENT or 1.0)
    if exp <= 0:
        exp = 1.0
    scaled = float(math.pow(raw, exp))
    m_min = float(ECONOMY_PRICE_MULTIPLIER_MIN or 0)
    m_max = float(ECONOMY_PRICE_MULTIPLIER_MAX or 0)
    if m_min > 0 and scaled < m_min:
        scaled = m_min
    if m_max > 0 and scaled > m_max:
        scaled = m_max
    return float(scaled)


                          
SHOP_ITEMS: Dict[str, ShopItem] = {
                                                                                
    'rig_basic': ShopItem(
        id='rig_basic',
        name='Veddha V3D Mining Frame (GPU)',
        price=100,
        description='Базовый открытый каркас для видеокарт. Поддержка до 1 видеокарты. Простая конструкция для начинающих.',
        item_type='rig',
        effects={'hashrate': 0, 'power_consumption': 10, 'heat': 5, 'psu_power': 0, 'cooling': 0},
        gpu_slots=1,
    ),
    'rig_advanced': ShopItem(
        id='rig_advanced',
        name='Veddha V8 Mining Frame (GPU)',
        price=400,
        description='Улучшенный каркас с усиленной вентиляцией для видеокарт. Поддержка до 3 видеокарт. Оптимизирован для средних ферм.',
        item_type='rig',
        effects={'hashrate': 0, 'power_consumption': 20, 'heat': 10, 'psu_power': 0, 'cooling': -5},
        gpu_slots=3,
    ),
    'rig_professional': ShopItem(
        id='rig_professional',
        name='Veddha V8 PRO Mining Frame (GPU)',
        price=1000,
        description='Профессиональный каркас с интегрированной системой охлаждения для видеокарт. Поддержка до 6 видеокарт. Для серьезных майнеров.',
        item_type='rig',
        effects={'hashrate': 0, 'power_consumption': 30, 'heat': 15, 'psu_power': 0, 'cooling': -15},
        gpu_slots=6,
    ),

                                                                         
    'asic_rig_basic': ShopItem(
        id='asic_rig_basic',
        name='ASIC Mining Rack Basic',
        price=200,
        description='Базовый стеллаж для ASIC майнеров. Поддержка до 1 ASIC устройства. Прочная конструкция для начинающих.',
        item_type='asic_rig',
        effects={'hashrate': 0, 'power_consumption': 15, 'heat': 10, 'psu_power': 0, 'cooling': 0},
        asic_slots=1,
    ),
    'asic_rig_advanced': ShopItem(
        id='asic_rig_advanced',
        name='ASIC Mining Rack Advanced',
        price=800,
        description='Улучшенный стеллаж для ASIC майнеров. Поддержка до 3 ASIC устройств. Усиленная вентиляция для средних ферм.',
        item_type='asic_rig',
        effects={'hashrate': 0, 'power_consumption': 30, 'heat': 20, 'psu_power': 0, 'cooling': -10},
        asic_slots=3,
    ),
    'asic_rig_professional': ShopItem(
        id='asic_rig_professional',
        name='ASIC Mining Rack Professional',
        price=2000,
        description='Профессиональный стеллаж для ASIC майнеров. Поддержка до 6 ASIC устройств. Интегрированное охлаждение для крупных ферм.',
        item_type='asic_rig',
        effects={'hashrate': 0, 'power_consumption': 50, 'heat': 30, 'psu_power': 0, 'cooling': -25},
        asic_slots=6,
    ),

                                                                                       
                                              
    'gpu_gt730': ShopItem(
        id='gpu_gt730',
        name='NVIDIA GeForce GT 730',
        price=60,
        description='Самая бюджетная карта. Минимальный хешрейт, но и минимальное потребление. Для самых экономных.',
        item_type='gpu',
        effects={'hashrate': 20, 'power_consumption': 25, 'heat': 2, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_gt1030': ShopItem(
        id='gpu_gt1030',
        name='NVIDIA GeForce GT 1030',
        price=100,
        description='Ультрабюджетная видеокарта. Подходит для начала майнинга с минимальными вложениями.',
        item_type='gpu',
        effects={'hashrate': 40, 'power_consumption': 30, 'heat': 4, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_gtx1050': ShopItem(
        id='gpu_gtx1050',
        name='NVIDIA GeForce GTX 1050',
        price=140,
        description='Начальная игровая карта с базовым хешрейтом. Хороший старт для новичков.',
        item_type='gpu',
        effects={'hashrate': 70, 'power_consumption': 55, 'heat': 7, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_basic': ShopItem(
        id='gpu_basic',
        name='NVIDIA GeForce GTX 1050 Ti',
        price=200,
        description='Бюджетная видеокарта для майнинга. Низкое энергопотребление, подходит для начинающих майнеров.',
        item_type='gpu',
        effects={'hashrate': 100, 'power_consumption': 75, 'heat': 10, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_gtx1060': ShopItem(
        id='gpu_gtx1060',
        name='NVIDIA GeForce GTX 1060 6GB',
        price=260,
        description='Популярная карта прошлых лет. Хорошее соотношение цена/производительность для бюджетного майнинга.',
        item_type='gpu',
        effects={'hashrate': 140, 'power_consumption': 100, 'heat': 14, 'psu_power': 0, 'cooling': 0}
    ),
    
                                 
    'gpu_gtx1070': ShopItem(
        id='gpu_gtx1070',
        name='NVIDIA GeForce GTX 1070',
        price=360,
        description='Отличный выбор для майнинга. Высокая эффективность при умеренном потреблении.',
        item_type='gpu',
        effects={'hashrate': 200, 'power_consumption': 130, 'heat': 17, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_gtx1080': ShopItem(
        id='gpu_gtx1080',
        name='NVIDIA GeForce GTX 1080',
        price=440,
        description='Мощная карта прошлого поколения. Высокий хешрейт при разумном потреблении.',
        item_type='gpu',
        effects={'hashrate': 260, 'power_consumption': 150, 'heat': 21, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_rtx2060': ShopItem(
        id='gpu_rtx2060',
        name='NVIDIA GeForce RTX 2060',
        price=500,
        description='Карта с поддержкой RTX. Отличный баланс цены и производительности.',
        item_type='gpu',
        effects={'hashrate': 240, 'power_consumption': 160, 'heat': 22, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_medium': ShopItem(
        id='gpu_medium',
        name='NVIDIA GeForce RTX 3060',
        price=600,
        description='Средний класс видеокарты с хорошим соотношением цена/производительность. Отличный выбор для майнинга.',
        item_type='gpu',
        effects={'hashrate': 300, 'power_consumption': 170, 'heat': 25, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_rtx3060ti': ShopItem(
        id='gpu_rtx3060ti',
        name='NVIDIA GeForce RTX 3060 Ti',
        price=760,
        description='Улучшенная версия RTX 3060. Больше мощности при том же потреблении.',
        item_type='gpu',
        effects={'hashrate': 360, 'power_consumption': 190, 'heat': 27, 'psu_power': 0, 'cooling': 0}
    ),
    
                                     
    'gpu_rtx3070': ShopItem(
        id='gpu_rtx3070',
        name='NVIDIA GeForce RTX 3070',
        price=900,
        description='Высокопроизводительная карта для серьёзного майнинга. Отличная эффективность.',
        item_type='gpu',
        effects={'hashrate': 440, 'power_consumption': 220, 'heat': 32, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_rtx3070ti': ShopItem(
        id='gpu_rtx3070ti',
        name='NVIDIA GeForce RTX 3070 Ti',
        price=1040,
        description='Улучшенная версия RTX 3070. Ещё больше хешрейта для профессионалов.',
        item_type='gpu',
        effects={'hashrate': 500, 'power_consumption': 250, 'heat': 37, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_advanced': ShopItem(
        id='gpu_advanced',
        name='NVIDIA GeForce RTX 3080',
        price=1200,
        description='Мощная видеокарта для профессионального майнинга. Высокий хешрейт и надежность.',
        item_type='gpu',
        effects={'hashrate': 600, 'power_consumption': 320, 'heat': 50, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_rtx3080ti': ShopItem(
        id='gpu_rtx3080ti',
        name='NVIDIA GeForce RTX 3080 Ti',
        price=1500,
        description='Продвинутая версия RTX 3080. Максимум от поколения 30-й серии.',
        item_type='gpu',
        effects={'hashrate': 720, 'power_consumption': 350, 'heat': 55, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_rtx3090': ShopItem(
        id='gpu_rtx3090',
        name='NVIDIA GeForce RTX 3090',
        price=1800,
        description='Флагман 30-й серии. Огромный хешрейт для максимальной прибыли.',
        item_type='gpu',
        effects={'hashrate': 840, 'power_consumption': 400, 'heat': 60, 'psu_power': 0, 'cooling': 0}
    ),
    
                               
    'gpu_rtx4070': ShopItem(
        id='gpu_rtx4070',
        name='NVIDIA GeForce RTX 4070',
        price=2000,
        description='Новое поколение. Высокая эффективность благодаря архитектуре Ada Lovelace.',
        item_type='gpu',
        effects={'hashrate': 960, 'power_consumption': 350, 'heat': 45, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_rtx4080': ShopItem(
        id='gpu_rtx4080',
        name='NVIDIA GeForce RTX 4080',
        price=3000,
        description='Премиум-карта нового поколения. Невероятная производительность.',
        item_type='gpu',
        effects={'hashrate': 1100, 'power_consumption': 380, 'heat': 55, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_professional': ShopItem(
        id='gpu_professional',
        name='NVIDIA GeForce RTX 4090',
        price=4000,
        description='Топовая видеокарта с максимальной производительностью. Лучший выбор для серьезных майнинг-ферм.',
        item_type='gpu',
        effects={'hashrate': 1400, 'power_consumption': 450, 'heat': 75, 'psu_power': 0, 'cooling': 0}
    ),
    'gpu_rtx4090ti': ShopItem(
        id='gpu_rtx4090ti',
        name='NVIDIA GeForce RTX 4090 Ti',
        price=5600,
        description='Абсолютный флагман. Максимально возможный хешрейт от видеокарты.',
        item_type='gpu',
        effects={'hashrate': 1700, 'power_consumption': 500, 'heat': 85, 'psu_power': 0, 'cooling': 0}
    ),

                                                                                         
    'cooling_basic_fan': ShopItem(
        id='cooling_basic_fan',
        name='DeepCool XFAN 120',
        price=40,
        description='Базовый вентилятор 120мм. Минимальное охлаждение для небольших ферм.',
        item_type='cooling',
        effects={'hashrate': 0, 'power_consumption': 3, 'heat': 0, 'psu_power': 0, 'cooling': -5}
    ),
    'cooling_fan': ShopItem(
        id='cooling_fan',
        name='Arctic P12 PWM Fan',
        price=100,
        description='Базовый вентилятор 120мм с PWM управлением. Эффективное охлаждение при низком шуме.',
        item_type='cooling',
        effects={'hashrate': 0, 'power_consumption': 5, 'heat': 0, 'psu_power': 0, 'cooling': -10}
    ),
    'cooling_dual_fan': ShopItem(
        id='cooling_dual_fan',
        name='be quiet! Silent Wings 3 (x2)',
        price=180,
        description='Два премиальных тихих вентилятора. Отличное соотношение цена/эффективность.',
        item_type='cooling',
        effects={'hashrate': 0, 'power_consumption': 8, 'heat': 0, 'psu_power': 0, 'cooling': -20}
    ),
    'cooling_advanced': ShopItem(
        id='cooling_advanced',
        name='Noctua NF-A12x25 PWM',
        price=300,
        description='Премиум система воздушного охлаждения. Несколько вентиляторов с высоким статическим давлением.',
        item_type='cooling',
        effects={'hashrate': 0, 'power_consumption': 15, 'heat': 0, 'psu_power': 0, 'cooling': -30}
    ),
    'cooling_tower': ShopItem(
        id='cooling_tower',
        name='Noctua NH-D15 Tower Cooler',
        price=500,
        description='Массивный башенный кулер. Превосходное пассивное охлаждение.',
        item_type='cooling',
        effects={'hashrate': 0, 'power_consumption': 20, 'heat': 0, 'psu_power': 0, 'cooling': -50}
    ),
    'cooling_water': ShopItem(
        id='cooling_water',
        name='Corsair H150i Elite Capellix',
        price=800,
        description='Профессиональная система водяного охлаждения (AIO). Максимальная эффективность охлаждения для мощных ферм.',
        item_type='cooling',
        effects={'hashrate': 0, 'power_consumption': 30, 'heat': 0, 'psu_power': 0, 'cooling': -80}
    ),
    'cooling_custom_loop': ShopItem(
        id='cooling_custom_loop',
        name='EKWB Custom Loop Kit',
        price=1400,
        description='Кастомная система водяного охлаждения. Охлаждает всю ферму одновременно.',
        item_type='cooling',
        effects={'hashrate': 0, 'power_consumption': 50, 'heat': 0, 'psu_power': 0, 'cooling': -120}
    ),
    'cooling_industrial': ShopItem(
        id='cooling_industrial',
        name='Industrial Chiller Unit',
        price=3000,
        description='Промышленный чиллер. Экстремальное охлаждение для крупных майнинг-ферм.',
        item_type='cooling',
        effects={'hashrate': 0, 'power_consumption': 100, 'heat': 0, 'psu_power': 0, 'cooling': -250}
    ),

                                                                                          
    'psu_entry': ShopItem(
        id='psu_entry',
        name='EVGA 400 N1',
        price=120,
        description='Начальный блок питания 400W. Для самых маленьких ферм.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 350, 'cooling': 0}
    ),
    'psu_basic': ShopItem(
        id='psu_basic',
        name='Corsair CV550 80+ Bronze',
        price=240,
        description='Базовый блок питания 550W с сертификацией 80+ Bronze. Надежное питание для небольших ферм.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 500, 'cooling': 0}
    ),
    'psu_650w': ShopItem(
        id='psu_650w',
        name='Corsair RM650 80+ Gold',
        price=360,
        description='Качественный блок питания 650W. Золотой сертификат для надёжности.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 600, 'cooling': 0}
    ),
    'psu_750w': ShopItem(
        id='psu_750w',
        name='Seasonic Focus GX-750 80+ Gold',
        price=450,
        description='Надёжный блок питания 750W. Идеален для средних ферм.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 700, 'cooling': 0}
    ),
    'psu_850w': ShopItem(
        id='psu_850w',
        name='Corsair RM850x 80+ Gold',
        price=540,
        description='Мощный блок питания 850W. Для ферм с несколькими картами.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 800, 'cooling': 0}
    ),
    'psu_medium': ShopItem(
        id='psu_medium',
        name='Seasonic Focus GX-1000 80+ Gold',
        price=660,
        description='Мощный блок питания 1000W с сертификацией 80+ Gold. Высокая эффективность и надежность.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 1000, 'cooling': 0}
    ),
    'psu_1200w': ShopItem(
        id='psu_1200w',
        name='EVGA SuperNOVA 1200 P2 80+ Platinum',
        price=900,
        description='Профессиональный блок питания 1200W. Платиновая эффективность.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 1200, 'cooling': 0}
    ),
    'psu_advanced': ShopItem(
        id='psu_advanced',
        name='Corsair HX1500i 80+ Platinum',
        price=1350,
        description='Профессиональный блок питания 1500W с сертификацией 80+ Platinum. Для средних и больших ферм.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 1500, 'cooling': 0}
    ),
    'psu_1600w': ShopItem(
        id='psu_1600w',
        name='EVGA SuperNOVA 1600 T2 80+ Titanium',
        price=1650,
        description='Блок питания 1600W с титановой сертификацией. Максимальная эффективность.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 1600, 'cooling': 0}
    ),
    'psu_professional': ShopItem(
        id='psu_professional',
        name='Seasonic Prime TX-2000 80+ Titanium',
        price=2250,
        description='Топовый блок питания 2000W с сертификацией 80+ Titanium. Максимальная эффективность для крупных ферм.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 2000, 'cooling': 0}
    ),
    'psu_server_2400w': ShopItem(
        id='psu_server_2400w',
        name='HP Server PSU 2400W (Converted)',
        price=2700,
        description='Серверный блок питания, адаптированный для майнинга. Огромная мощность.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 2400, 'cooling': 0}
    ),
    'psu_mining_3000w': ShopItem(
        id='psu_mining_3000w',
        name='Mining Power 3000W Industrial',
        price=3600,
        description='Промышленный блок питания для майнинга 3000W. Для больших ASIC-ферм.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 3000, 'cooling': 0}
    ),
    'psu_mining_5000w': ShopItem(
        id='psu_mining_5000w',
        name='Industrial Mining PSU 5000W',
        price=6000,
        description='Мега-мощный промышленный БП 5000W. Питает несколько ASIC-майнеров одновременно.',
        item_type='psu',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 5000, 'cooling': 0}
    ),

                                                                                                     
                                     
    'asic_antminer_s9': ShopItem(
        id='asic_antminer_s9',
        name='Bitmain Antminer S9',
        price=2000,
        description='Легендарный ASIC майнер. Устаревшая, но надёжная модель для начала. Потребление: 1350W.',
        item_type='asic',
        effects={'hashrate': 1600, 'power_consumption': 1350, 'heat': 40, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_whatsminer_m20s': ShopItem(
        id='asic_whatsminer_m20s',
        name='MicroBT Whatsminer M20S',
        price=3200,
        description='Бюджетный ASIC от MicroBT. Хорошее начало для ASIC-майнинга. Потребление: 2100W.',
        item_type='asic',
        effects={'hashrate': 2400, 'power_consumption': 2100, 'heat': 60, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_antminer_s17': ShopItem(
        id='asic_antminer_s17',
        name='Bitmain Antminer S17',
        price=4800,
        description='Предыдущее поколение от Bitmain. Хорошая производительность. Потребление: 2800W.',
        item_type='asic',
        effects={'hashrate': 3200, 'power_consumption': 2800, 'heat': 75, 'psu_power': 0, 'cooling': 0}
    ),
    
                                     
    'asic_antminer_s19': ShopItem(
        id='asic_antminer_s19',
        name='Bitmain Antminer S19',
        price=8000,
        description='Профессиональный ASIC майнер от Bitmain. Высокая производительность для майнинга Bitcoin. Потребление: 3250W.',
        item_type='asic',
        effects={'hashrate': 4000, 'power_consumption': 3250, 'heat': 100, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_whatsminer_m30s': ShopItem(
        id='asic_whatsminer_m30s',
        name='MicroBT Whatsminer M30S',
        price=8800,
        description='Мощный ASIC от MicroBT. Конкурент Antminer S19. Потребление: 3400W.',
        item_type='asic',
        effects={'hashrate': 4400, 'power_consumption': 3400, 'heat': 105, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_whatsminer_m50': ShopItem(
        id='asic_whatsminer_m50',
        name='MicroBT Whatsminer M50',
        price=10000,
        description='ASIC майнер от MicroBT. Отличное соотношение цена/производительность. Потребление: 3420W.',
        item_type='asic',
        effects={'hashrate': 5000, 'power_consumption': 3420, 'heat': 110, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_antminer_s19j_pro': ShopItem(
        id='asic_antminer_s19j_pro',
        name='Bitmain Antminer S19j Pro',
        price=11200,
        description='Улучшенная версия S19. Оптимизированное энергопотребление. Потребление: 3500W.',
        item_type='asic',
        effects={'hashrate': 5600, 'power_consumption': 3500, 'heat': 115, 'psu_power': 0, 'cooling': 0}
    ),
    
                                         
    'asic_antminer_s19_pro': ShopItem(
        id='asic_antminer_s19_pro',
        name='Bitmain Antminer S19 Pro',
        price=14000,
        description='Улучшенная версия Antminer S19. Максимальная производительность и эффективность. Потребление: 3600W.',
        item_type='asic',
        effects={'hashrate': 7000, 'power_consumption': 3600, 'heat': 125, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_antminer_s19_xp': ShopItem(
        id='asic_antminer_s19_xp',
        name='Bitmain Antminer S19 XP',
        price=16000,
        description='Экстремальная версия S19. Максимум хешрейта от линейки S19. Потребление: 3700W.',
        item_type='asic',
        effects={'hashrate': 8000, 'power_consumption': 3700, 'heat': 130, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_whatsminer_m53': ShopItem(
        id='asic_whatsminer_m53',
        name='MicroBT Whatsminer M53',
        price=18000,
        description='Топовый ASIC майнер от MicroBT. Высокая эффективность и надежность. Потребление: 3800W.',
        item_type='asic',
        effects={'hashrate': 9000, 'power_consumption': 3800, 'heat': 140, 'psu_power': 0, 'cooling': 0}
    ),
    
                                 
    'asic_antminer_s21': ShopItem(
        id='asic_antminer_s21',
        name='Bitmain Antminer S21',
        price=22000,
        description='Новейший ASIC майнер от Bitmain. Революционная производительность. Потребление: 3900W.',
        item_type='asic',
        effects={'hashrate': 11000, 'power_consumption': 3900, 'heat': 150, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_antminer_s21_pro': ShopItem(
        id='asic_antminer_s21_pro',
        name='Bitmain Antminer S21 Pro',
        price=28000,
        description='Профессиональная версия S21. Ещё больше хешрейта. Потребление: 4100W.',
        item_type='asic',
        effects={'hashrate': 14000, 'power_consumption': 4100, 'heat': 160, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_antminer_s21_hydro': ShopItem(
        id='asic_antminer_s21_hydro',
        name='Bitmain Antminer S21 Hydro',
        price=36000,
        description='Версия с водяным охлаждением. Минимальный нагрев, максимальный хешрейт. Потребление: 4300W.',
        item_type='asic',
        effects={'hashrate': 18000, 'power_consumption': 4300, 'heat': 75, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_whatsminer_m60': ShopItem(
        id='asic_whatsminer_m60',
        name='MicroBT Whatsminer M60',
        price=40000,
        description='Флагман от MicroBT. Экстремальная производительность. Потребление: 4500W.',
        item_type='asic',
        effects={'hashrate': 20000, 'power_consumption': 4500, 'heat': 175, 'psu_power': 0, 'cooling': 0}
    ),
    'asic_antminer_s21_ultimate': ShopItem(
        id='asic_antminer_s21_ultimate',
        name='Bitmain Antminer S21 Ultimate',
        price=60000,
        description='Абсолютный флагман. Максимально возможный хешрейт. Потребление: 4700W.',
        item_type='asic',
        effects={'hashrate': 30000, 'power_consumption': 4700, 'heat': 200, 'psu_power': 0, 'cooling': 0}
    ),

                                                                   
    'consumable_water': ShopItem(
        id='consumable_water',
        name='Дистиллированная вода для СВО (1л)',
        price=20,
        description='Расходный материал для систем водяного охлаждения. Регулярная замена обеспечивает эффективное охлаждение.',
        item_type='consumable',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 0, 'cooling': -5}
    ),
    'consumable_air': ShopItem(
        id='consumable_air',
        name='Баллон со сжатым воздухом',
        price=100,
        description='Сжатый воздух для чистки фермы. Полностью удаляет пыль со всего оборудования и снижает температуру.',
        item_type='consumable',
        effects={'hashrate': 0, 'power_consumption': 0, 'heat': 0, 'psu_power': 0, 'cooling': 0}
    ),
}

_DEFAULT_PRICE_PIVOT: float = 500.0
_DEFAULT_PRICE_SCALE: float = 2.0
_DEFAULT_PRICE_POWER: float = 0.25

_PRICE_PARAMS_BY_TYPE = {
    "gpu": (500.0, 2.2, 0.25),
    "asic": (500.0, 2.35, 0.27),
    "psu": (500.0, 1.6, 0.12),
    "rig": (500.0, 1.7, 0.20),
    "asic_rig": (500.0, 1.7, 0.20),
    "cooling": (500.0, 1.6, 0.18),
    "consumable": (500.0, 1.0, 0.0),
}


def _scale_price(p: float, *, pivot: float, scale: float, power: float) -> int:
    price = float(p or 0)
    if price <= 0:
        return 1
    if power == 0:
        factor = 1.0
    else:
        factor = (price / float(pivot)) ** float(power)
    return max(1, int(round(price * float(scale) * factor)))


def _scale_item_price(item: ShopItem) -> int:
    pivot, scale, power = _PRICE_PARAMS_BY_TYPE.get(
        item.item_type,
        (_DEFAULT_PRICE_PIVOT, _DEFAULT_PRICE_SCALE, _DEFAULT_PRICE_POWER),
    )

    if item.item_type in ("rig", "asic_rig"):
        slots = int((item.gpu_slots if item.item_type == "rig" else item.asic_slots) or 0)
        slots = max(1, slots)
        per_slot = float(item.price or 0) / float(slots)
        return _scale_price(per_slot, pivot=pivot, scale=scale, power=power) * slots

    return _scale_price(item.price, pivot=pivot, scale=scale, power=power)


for _item in SHOP_ITEMS.values():
    _item.price = _scale_item_price(_item)


_BASE_PRICES_USD: Dict[str, float] = {k: float(v.price or 0) for k, v in SHOP_ITEMS.items()}


def get_item_price_usd(item_id: str, *, rate_usd_per_btc: Optional[float] = None) -> int:
    base = float(_BASE_PRICES_USD.get(str(item_id), 0) or 0)
    if base <= 0:
        base = float(getattr(SHOP_ITEMS.get(str(item_id)), "price", 0) or 0)
    price = base * _get_price_multiplier(rate_usd_per_btc=rate_usd_per_btc)
    return max(1, _round_up_to_step(price, PRICE_ROUND_STEP_USD))


def get_starter_balance_usd(*, rate_usd_per_btc: Optional[float] = None) -> int:
    total = 0
    for item_id in ("rig_basic", "gpu_gt730", "psu_entry", "cooling_basic_fan"):
        total += int(get_item_price_usd(item_id, rate_usd_per_btc=rate_usd_per_btc) or 0)
    total = int(math.ceil(float(total) * 1.1))
    return max(1, _round_up_to_step(float(total), PRICE_ROUND_STEP_USD))

                                                                
SHOP_CATEGORIES = {
    'rigs': ['rig_basic', 'rig_advanced', 'rig_professional'],
    'asic_rigs': ['asic_rig_basic', 'asic_rig_advanced', 'asic_rig_professional'],
    'gpu': [
        'gpu_gt730', 'gpu_gt1030', 'gpu_gtx1050', 'gpu_basic', 'gpu_gtx1060',
        'gpu_gtx1070', 'gpu_gtx1080', 'gpu_rtx2060', 'gpu_medium', 'gpu_rtx3060ti',
        'gpu_rtx3070', 'gpu_rtx3070ti', 'gpu_advanced', 'gpu_rtx3080ti', 'gpu_rtx3090',
        'gpu_rtx4070', 'gpu_rtx4080', 'gpu_professional', 'gpu_rtx4090ti'
    ],
    'asic': [
        'asic_antminer_s9', 'asic_whatsminer_m20s', 'asic_antminer_s17',
        'asic_antminer_s19', 'asic_whatsminer_m30s', 'asic_whatsminer_m50', 'asic_antminer_s19j_pro',
        'asic_antminer_s19_pro', 'asic_antminer_s19_xp', 'asic_whatsminer_m53',
        'asic_antminer_s21', 'asic_antminer_s21_pro', 'asic_antminer_s21_hydro',
        'asic_whatsminer_m60', 'asic_antminer_s21_ultimate'
    ],
    'cooling': [
        'cooling_basic_fan', 'cooling_fan', 'cooling_dual_fan', 'cooling_advanced',
        'cooling_tower', 'cooling_water', 'cooling_custom_loop', 'cooling_industrial'
    ],
    'psu': [
        'psu_entry', 'psu_basic', 'psu_650w', 'psu_750w', 'psu_850w',
        'psu_medium', 'psu_1200w', 'psu_advanced', 'psu_1600w', 'psu_professional',
        'psu_server_2400w', 'psu_mining_3000w', 'psu_mining_5000w'
    ],
    'consumables': ['consumable_water', 'consumable_air'],
}

CATEGORY_NAMES = {
    'rigs': '🖥️ Каркасы для видеокарт (GPU)',
    'asic_rigs': '📦 Корпуса для ASIC майнеров',
    'gpu': '🎮 Видеокарты (GPU)',
    'asic': '⚙️ ASIC майнеры',
    'cooling': '❄️ Системы охлаждения',
    'psu': '⚡ Блоки питания',
    'consumables': '💧 Расходные материалы',
}

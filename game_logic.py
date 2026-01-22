import math
from datetime import datetime, timedelta
from typing import Dict, Tuple
from database import db
from models import SHOP_ITEMS, get_item_price_usd
from exchange_rate import get_bitcoin_exchange_rate
from config import BASE_HASHRATE

                                                                  
DUST_GROWTH_PER_HOUR: float = 2.5                                                    


AMBIENT_TEMP_C: float = 25.0
TEMP_RISE_SCALE: float = 12.0
                                                                 
POWER_TO_HEAT_FACTOR: float = 0.02
                               
DUST_TEMP_PER_PERCENT: float = 0.20

                                                     
TEMP_WARM_C: float = 70.0
TEMP_HOT_C: float = 80.0
TEMP_OVERHEAT_C: float = 90.0
TEMP_CRITICAL_C: float = 100.0


MAX_MINING_WINDOW_SECONDS: float = 6 * 3600
MINING_HASHRATE_EXPONENT: float = 0.85
BTC_PER_HOUR_PER_HASHRATE_UNIT: float = 0.00001


def calculate_effective_temperature(stats: Dict, dust_level: float) -> float:
    heat_generation = float(stats.get("heat_generation", 0) or 0)
    cooling_eff = float(stats.get("cooling_efficiency", 0) or 0)
    power_consumption = float(stats.get("power_consumption", 0) or 0)

                                                                                                 
                                                                 
    if heat_generation == 0.0 and cooling_eff == 0.0 and power_consumption == 0.0:
        return 0.0

    heat_index = heat_generation + power_consumption * POWER_TO_HEAT_FACTOR
    if heat_index < 0:
        heat_index = 0.0

    temp_rise = TEMP_RISE_SCALE * math.log1p(float(heat_index))
    temp = (
        AMBIENT_TEMP_C
        + temp_rise
        + float(max(0.0, float(dust_level or 0))) * DUST_TEMP_PER_PERCENT
        + cooling_eff
    )
    if temp < AMBIENT_TEMP_C:
        temp = AMBIENT_TEMP_C
    return float(temp)


def heat_penalty_factor(temp_c: float) -> float:
    t = float(temp_c or 0)
    if t >= TEMP_CRITICAL_C:
        return 0.3
    if t >= TEMP_OVERHEAT_C:
        return 0.6
    if t >= TEMP_HOT_C:
        return 0.8
    if t >= TEMP_WARM_C:
        return 0.9
    return 1.0


def validate_rig_configuration(user_id: int) -> Tuple[bool, str]:
    installed_items = db.get_installed_items(user_id)

    total_gpu_slots = 0
    total_gpus_installed = 0
    total_asic_slots = 0
    total_asics_installed = 0

    for item in installed_items:
        item_data = SHOP_ITEMS.get(item["item_id"])
        if not item_data:
            continue

        qty = item.get("quantity", 0) or 0
        if qty <= 0:
            continue

        if item["item_type"] == "rig":
            total_gpu_slots += (getattr(item_data, "gpu_slots", 0) or 0) * qty
        elif item["item_type"] == "gpu":
            total_gpus_installed += qty
        elif item["item_type"] == "asic_rig":
            total_asic_slots += (getattr(item_data, "asic_slots", 0) or 0) * qty
        elif item["item_type"] == "asic":
            total_asics_installed += qty

    if total_asics_installed > 0:
        if total_asic_slots <= 0:
            return False, (
                "❌ Корпус для ASIC майнеров был отключён.\n\n"
                "⛔ Майнинг остановлен.\n"
                "✅ Установите корпус для ASIC майнеров, чтобы ферма могла работать."
            )
        if total_asics_installed > total_asic_slots:
            return False, (
                "❌ Недостаточно мест в корпусах для ASIC майнеров.\n\n"
                f"📦 Всего слотов для ASIC: {total_asic_slots}\n"
                f"⚙️ Установлено ASIC: {total_asics_installed}\n\n"
                "✅ Установите дополнительный корпус для ASIC майнеров."
            )

    if total_gpus_installed > 0:
        if total_gpu_slots <= 0:
            return False, (
                "❌ Корпус для видеокарт был отключён.\n\n"
                "⛔ Майнинг остановлен.\n"
                "✅ Установите корпус для видеокарт, чтобы ферма могла работать."
            )
        if total_gpus_installed > total_gpu_slots:
            return False, (
                "❌ Недостаточно слотов в корпусах для видеокарт.\n\n"
                f"📦 Всего слотов для GPU: {total_gpu_slots}\n"
                f"⚙️ Установлено GPU: {total_gpus_installed}\n\n"
                "✅ Установите дополнительный корпус для видеокарт."
            )

    return True, ""


def calculate_user_stats(user_id: int) -> Dict:
    installed_items = db.get_installed_items(user_id)
    user = db.get_user(user_id)
    
    if not user:
        return {
            'hashrate': 0,
            'power_consumption': 0,
            'heat_generation': 0,
            'psu_power': 0,
            'cooling_efficiency': 0
        }
    
    stats = {
        'hashrate': float(BASE_HASHRATE or 0),
        'power_consumption': 0,
        'heat_generation': 0,
        'psu_power': 0,
        'cooling_efficiency': 0
    }
    
                                                      
    for item in installed_items:
        item_data = SHOP_ITEMS.get(item['item_id'])
        if not item_data:
            continue
        
        quantity = item['quantity']
        
                                                       
        stats['hashrate'] += item_data.effects.get('hashrate', 0) * quantity
        stats['power_consumption'] += item_data.effects.get('power_consumption', 0) * quantity
        stats['heat_generation'] += item_data.effects.get('heat', 0) * quantity
        stats['psu_power'] += item_data.effects.get('psu_power', 0) * quantity
        stats['cooling_efficiency'] += item_data.effects.get('cooling', 0) * quantity
    
    return stats


def calculate_mining_reward(user_id: int) -> float:
    user = db.get_user(user_id)
    if not user:
        return 0.0
    
                                   
    mining_enabled = (user.get('mining_enabled', 0) or 0) == 1
    if not mining_enabled:
        return 0.0

    rig_ok, _rig_error = validate_rig_configuration(user_id)
    if not rig_ok:
        return 0.0
    
                                 
    stats = calculate_user_stats(user_id)
    hashrate = float(stats.get('hashrate', 0) or 0)
    if hashrate <= 0:
        return 0.0

    power_consumption = float(stats.get('power_consumption', 0) or 0)
    psu_power = float(stats.get('psu_power', 0) or 0)

                                                                       
    if power_consumption > 0 and (psu_power <= 0 or power_consumption > psu_power):
        return 0.0
    
    now = datetime.now()

                              
    last_collect = user.get('last_collect_time')
    if last_collect:
        if isinstance(last_collect, str):
            last_collect = datetime.fromisoformat(last_collect)
        elif not isinstance(last_collect, datetime):
            last_collect = now
    else:
        last_collect = now

    time_diff = max(0.0, (now - last_collect).total_seconds())
    time_diff = min(time_diff, MAX_MINING_WINDOW_SECONDS)

                                                                  
    dust_level, dust_last_update = db.get_dust_state(user_id)
    dust_level_before = dust_level
    if dust_last_update is None:
        dust_last_update = now
        db.update_dust_state(user_id, dust_level, dust_last_update)
    hours_since_dust_update = max(0.0, (now - dust_last_update).total_seconds() / 3600)
    if hours_since_dust_update > 0:
        hours_since_dust_update = min(hours_since_dust_update, MAX_MINING_WINDOW_SECONDS / 3600)
        dust_level = min(100.0, dust_level + hours_since_dust_update * DUST_GROWTH_PER_HOUR)
        db.update_dust_state(user_id, dust_level, now)

    temp_before = calculate_effective_temperature(stats, dust_level_before)
    temp_after = calculate_effective_temperature(stats, dust_level)
    penalty_before = heat_penalty_factor(temp_before)
    penalty_after = heat_penalty_factor(temp_after)
    hashrate *= (penalty_before + penalty_after) / 2.0
    
                                      
    if hashrate <= 0:
        return 0.0
    
                                                          
    hashrate_multiplier = db.get_hashrate_multiplier_for_user(user_id)
    hashrate *= hashrate_multiplier
    
    hashrate = math.pow(float(hashrate), MINING_HASHRATE_EXPONENT) if hashrate > 0 else 0.0

    hours = time_diff / 3600
    reward = hashrate * hours * BTC_PER_HOUR_PER_HASHRATE_UNIT
    
    return max(0.0, reward)


def get_pending_bitcoin(user_id: int, update_db: bool = True) -> float:
    user = db.get_user(user_id)
    if not user:
        return 0.0
    
                                   
    mining_enabled = (user.get('mining_enabled', 0) or 0) == 1
    
                                       
    new_reward = calculate_mining_reward(user_id)
    old_pending = user.get('pending_bitcoin', 0) or 0
    total_pending = old_pending + new_reward

                                                              
    try:
        dust_level_now, _ = db.get_dust_state(user_id)
        stats_now = calculate_user_stats(user_id)
        effective_temp_now = calculate_effective_temperature(stats_now, dust_level_now)
        mining_enabled_now = (user.get('mining_enabled', 0) or 0) == 1
        if mining_enabled_now and effective_temp_now >= TEMP_CRITICAL_C:
            now_dt = datetime.now()
            stats_now['pending_bitcoin'] = total_pending
            stats_now['last_collect_time'] = now_dt
            db.update_user_stats(user_id, stats_now)
            db.set_mining_enabled(user_id, False)
            return float(total_pending)
    except Exception:
        pass
    
                                         
    if update_db:
        stats = calculate_user_stats(user_id)
        stats['pending_bitcoin'] = total_pending
        stats['last_collect_time'] = datetime.now()
        db.update_user_stats(user_id, stats)
    
    return total_pending


def collect_bitcoin(user_id: int) -> float:
    pending = get_pending_bitcoin(user_id)
    
    if pending > 0:
                                   
        db.update_bitcoin_balance(user_id, pending)
        
                                                   
        stats = calculate_user_stats(user_id)
        stats['pending_bitcoin'] = 0
        stats['last_collect_time'] = datetime.now()
        db.update_user_stats(user_id, stats)
    
    return pending


def exchange_bitcoin_to_usd(user_id: int, bitcoin_amount: float) -> Tuple[bool, str, float]:
    user = db.get_user(user_id)
    if not user:
        return False, "Пользователь не найден", 0.0
    
    bitcoin_balance = user.get('bitcoin_balance', 0) or 0
    
    if bitcoin_amount <= 0:
        return False, "Сумма должна быть больше нуля", 0.0
    
    if bitcoin_balance < bitcoin_amount:
        return False, f"Недостаточно биткойна! У вас {bitcoin_balance:.8f} BTC", 0.0
    
                                        
    rate = get_bitcoin_exchange_rate()
    usd_amount = bitcoin_amount * rate
    
                                       
    db.update_bitcoin_balance(user_id, -bitcoin_amount)
    db.update_user_balance(user_id, usd_amount)
    
    return True, f"✅ Обменено {bitcoin_amount:.8f} BTC на {usd_amount:.2f} USD", usd_amount


def buy_item(user_id: int, item_id: str) -> Tuple[bool, str]:
    user = db.get_user(user_id)
    if not user:
        return False, "Пользователь не найден"
    
    item = SHOP_ITEMS.get(item_id)
    if not item:
        return False, "Товар не найден"

    price_usd = float(get_item_price_usd(item_id) or 0)
    
    balance = user.get('balance', 0) or 0
    if balance < price_usd:
        return False, f"Недостаточно средств! Нужно {price_usd:.0f} USD, у вас {balance:.2f} USD"
    
                      
    db.update_user_balance(user_id, -price_usd)
    
                                                      
    db.add_item_to_inventory(user_id, item_id, item.name, item.item_type)
    
    return True, f"✅ {item.name} успешно куплен и добавлен в инвентарь!"


def has_required_rig(user_id: int, item_type: str) -> Tuple[bool, str]:
    installed_items = db.get_installed_items(user_id)
    
                                                                            
    if item_type == 'gpu':
        total_gpu_slots = 0
        total_gpus_installed = 0
        
        for item in installed_items:
            item_data = SHOP_ITEMS.get(item["item_id"])
            if not item_data:
                continue

            qty = item.get("quantity", 0) or 0

            if item["item_type"] == "rig":
                                            
                total_gpu_slots += (getattr(item_data, "gpu_slots", 0) or 0) * qty
            elif item["item_type"] == "gpu":
                total_gpus_installed += qty

        if total_gpu_slots <= 0:
            return False, (
                "❌ Для установки видеокарты необходим корпус для GPU!\n\n"
                "🛒 Купите корпус в магазине (категория 'Каркасы для видеокарт')."
            )

                                                                                  
        if total_gpus_installed + 1 > total_gpu_slots:
            return False, (
                "❌ Недостаточно свободных слотов в корпусах для видеокарт!\n\n"
                f"📦 Всего слотов для GPU: {total_gpu_slots}\n"
                f"⚙️ Уже установлено видеокарт: {total_gpus_installed}\n\n"
                "🛒 Купите дополнительный корпус в магазине, чтобы установить больше видеокарт."
            )

        return True, ""
    
                                                                               
    elif item_type == 'asic':
        total_asic_slots = 0
        total_asics_installed = 0
        
        for item in installed_items:
            item_data = SHOP_ITEMS.get(item["item_id"])
            if not item_data:
                continue

            qty = item.get("quantity", 0) or 0

            if item["item_type"] == "asic_rig":
                total_asic_slots += (getattr(item_data, "asic_slots", 0) or 0) * qty
            elif item["item_type"] == "asic":
                total_asics_installed += qty

        if total_asic_slots <= 0:
            return False, (
                "❌ Для установки ASIC майнера необходим корпус для ASIC!\n\n"
                "🛒 Купите корпус в магазине (категория 'Корпуса для ASIC майнеров')."
            )

        if total_asics_installed + 1 > total_asic_slots:
            return False, (
                "❌ Недостаточно свободных мест в корпусах для ASIC майнеров!\n\n"
                f"📦 Всего слотов для ASIC: {total_asic_slots}\n"
                f"⚙️ Уже установлено ASIC майнеров: {total_asics_installed}\n\n"
                "🛒 Купите дополнительный корпус для ASIC в магазине."
            )

        return True, ""
    
                                             
    return True, ""


def install_item_from_inventory(user_id: int, item_id: str, quantity: int = 1) -> Tuple[bool, str]:
    inventory = db.get_user_inventory(user_id)
    
                                   
    item_in_inventory = None
    for item in inventory:
        if item['item_id'] == item_id and item['quantity'] >= quantity:
            item_in_inventory = item
            break
    
    if not item_in_inventory:
        return False, f"❌ Недостаточно предметов в инвентаре!"
    
                              
    item_data = SHOP_ITEMS.get(item_id)
    if not item_data:
        return False, "Предмет не найден"

    if item_data.item_type == "consumable":
        return False, "❌ Этот предмет нельзя установить. Используйте его в инвентаре."
    
                                                             
    has_rig, rig_error = has_required_rig(user_id, item_data.item_type)
    if not has_rig:
        return False, rig_error
    
                                         
    stats = calculate_user_stats(user_id)
    new_stats = {
        'hashrate': stats['hashrate'] + item_data.effects.get('hashrate', 0) * quantity,
        'power_consumption': stats['power_consumption'] + item_data.effects.get('power_consumption', 0) * quantity,
        'heat_generation': stats['heat_generation'] + item_data.effects.get('heat', 0) * quantity,
        'psu_power': stats['psu_power'] + item_data.effects.get('psu_power', 0) * quantity,
        'cooling_efficiency': stats['cooling_efficiency'] + item_data.effects.get('cooling', 0) * quantity
    }
    
                                                                                
    if item_data.effects.get('power_consumption', 0) > 0:
        if new_stats['power_consumption'] > new_stats['psu_power'] and new_stats['psu_power'] > 0:
            return False, f"⚠️ Недостаточно мощности БП! Требуется {new_stats['power_consumption']:.0f}W, доступно {new_stats['psu_power']:.0f}W"

    if db.is_mining_enabled(user_id):
        get_pending_bitcoin(user_id, update_db=True)
    
                           
    db.install_item(user_id, item_id, item_data.name, item_data.item_type, quantity)
    
                          
    final_stats = calculate_user_stats(user_id)
    user_after = db.get_user(user_id) or {}
    final_stats['pending_bitcoin'] = float(user_after.get('pending_bitcoin', 0) or 0)
    final_stats['last_collect_time'] = datetime.now()
    db.update_user_stats(user_id, final_stats)
    
    return True, f"✅ {item_data.name} установлен на ферму!"


def uninstall_item_from_farm(user_id: int, item_id: str, quantity: int = 1) -> Tuple[bool, str]:
    installed_items = db.get_installed_items(user_id)
    
                                
    item_installed = None
    for item in installed_items:
        if item['item_id'] == item_id and item['quantity'] >= quantity:
            item_installed = item
            break
    
    if not item_installed:
        return False, f"❌ Недостаточно установленных предметов!"
    
    item_data = SHOP_ITEMS.get(item_id)
    item_type = item_data.item_type if item_data else (item_installed.get("item_type") if item_installed else "")

    if db.is_mining_enabled(user_id):
        get_pending_bitcoin(user_id, update_db=True)

                     
    db.uninstall_item(user_id, item_id, quantity)

    force_stop_reason: str | None = None
    if item_type in ("asic_rig", "rig"):
        rig_ok_after, rig_error_after = validate_rig_configuration(user_id)
        if not rig_ok_after:
            if db.is_mining_enabled(user_id):
                db.set_mining_enabled(user_id, False)
            force_stop_reason = rig_error_after

    if item_type == "psu" and force_stop_reason is None:
        stats_after = calculate_user_stats(user_id)
        power_consumption = float(stats_after.get("power_consumption", 0) or 0)
        psu_power = float(stats_after.get("psu_power", 0) or 0)
        if power_consumption > 0 and (psu_power <= 0 or power_consumption > psu_power):
            if db.is_mining_enabled(user_id):
                db.set_mining_enabled(user_id, False)
            force_stop_reason = (
                "❌ Недостаточно мощности БП.\n\n"
                "⛔ Майнинг остановлен.\n"
                "✅ Установите более мощный блок питания."
            )
    
                          
    final_stats = calculate_user_stats(user_id)
    user_after = db.get_user(user_id) or {}
    final_stats['pending_bitcoin'] = float(user_after.get('pending_bitcoin', 0) or 0)
    final_stats['last_collect_time'] = datetime.now()
    db.update_user_stats(user_id, final_stats)
    
    item_name = item_data.name if item_data else item_id

    if force_stop_reason is not None:
        return True, f"✅ {item_name} снят с фермы и возвращен в инвентарь!\n\n{force_stop_reason}"

    return True, f"✅ {item_name} снят с фермы и возвращен в инвентарь!"


def get_mining_status_text(user_id: int) -> str:
    user = db.get_user(user_id)
    if not user:
        return "Ошибка: пользователь не найден"

    stats = calculate_user_stats(user_id)
    pending_btc = get_pending_bitcoin(user_id, update_db=False)
    balance = user.get("balance", 0) or 0
    mining_enabled = (user.get("mining_enabled", 0) or 0) == 1

                          
    dust_level, _ = db.get_dust_state(user_id)

    rig_ok, rig_error = validate_rig_configuration(user_id)

    effective_temp = calculate_effective_temperature(stats, dust_level)

    power_consumption = float(stats.get("power_consumption", 0) or 0)
    psu_power = float(stats.get("psu_power", 0) or 0)

    power_ok = True
    if power_consumption > 0 and (psu_power <= 0 or power_consumption > psu_power):
        power_ok = False

    heat_penalty = heat_penalty_factor(effective_temp)
    effective_hashrate_hs = float(stats.get("hashrate", 0) or 0)
    if not mining_enabled or not power_ok:
        effective_hashrate_hs = 0.0
    else:
        effective_hashrate_hs *= heat_penalty

            
    if effective_temp >= TEMP_CRITICAL_C:
        status_icon = "🔥"
        status_text = "Критический перегрев"
    elif not rig_ok:
        status_icon = "⛔"
        status_text = "Требуется корпус"
    elif not mining_enabled:
        status_icon = "🔴"
        status_text = "Остановлена"
    elif not power_ok:
        status_icon = "⚡"
        status_text = "Нет питания"
    elif effective_temp >= TEMP_OVERHEAT_C:
        status_icon = "🌡️"
        status_text = "Перегрев"
    else:
        status_icon = "🟢"
        status_text = "Работает"

                          
    if effective_temp >= TEMP_OVERHEAT_C:
        temp_icon = "🔥"
    elif effective_temp >= TEMP_HOT_C:
        temp_icon = "🌡️"
    elif effective_temp > 25:
        temp_icon = "❄️"
    else:
        temp_icon = "❄️"

             
    power_str = f"{power_consumption:.0f} / {psu_power:.0f} W"

                                                       
    hashrate_hs = effective_hashrate_hs
    if hashrate_hs >= 1_000_000_000_000:
        hashrate_str = f"{hashrate_hs / 1_000_000_000_000:.3f} TH/s"
    elif hashrate_hs >= 1_000_000_000:
        hashrate_str = f"{hashrate_hs / 1_000_000_000:.3f} GH/s"
    else:
        hashrate_str = f"{hashrate_hs:.2f} H/s"

                                      
    filled_segments = int(dust_level // 10)
    bar = "█" * filled_segments + "░" * (10 - filled_segments)

    lines: list[str] = []
    lines.append("🖥 <b>Панель управления</b>")
    lines.append(f"Status: {status_icon} <b>{status_text}</b>")

             
    lines.append("\n🧊 <b>Система</b>")
    lines.append(f"• Темп: {effective_temp:.1f}°C {temp_icon}")
    lines.append(f"• Питание: {power_str} ⚡")
    lines.append(f"• Пыль: {bar} {int(dust_level)}%")

             
    lines.append("\n💳 <b>Финансы</b>")
    lines.append(f"• Баланс: {balance:.2f} USD")

             
    lines.append("\n⛏ <b>Майнинг</b>")
    if not rig_ok:
        lines.append("• Сейчас: <b>остановлена</b>")
        lines.append("• Причина: <b>корпус отключён</b>")
        if rig_error:
            lines.append(f"• Что делать: {rig_error.splitlines()[-1]}")
    elif not mining_enabled:
        lines.append("• Сейчас: <b>выключена</b>")
    else:
        lines.append(f"• Хешрейт: {hashrate_str}")
        if power_ok:
            efficiency_pct = int(round(heat_penalty * 100))
            lines.append(f"• Эффективность: {efficiency_pct}%")

            if efficiency_pct < 100:
                if effective_temp > 100:
                    lines.append("• Причина: <b>критический перегрев</b>")
                    lines.append("• Как поднять: добавьте охлаждение и очистите ферму от пыли")
                elif effective_temp > 70:
                    lines.append("• Причина: <b>перегрев</b>")
                    lines.append("• Как поднять: добавьте охлаждение и очистите ферму от пыли")
                else:
                    lines.append("• Причина: <b>нагрев</b>")
                    lines.append("• Как поднять: улучшите охлаждение и снизьте температуру")
        else:
            lines.append("• Эффективность: 0%")
            lines.append("• Причина: <b>нехватка мощности БП</b>")
            lines.append("• Как поднять: установите/добавьте блоки питания или снимите часть оборудования")

    return "\n".join(lines)


def repair_equipment_from_inventory(user_id: int, item_id: str, quantity: int = 1) -> Tuple[bool, str, float]:
    user = db.get_user(user_id)
    if not user:
        return False, "Пользователь не найден", 0.0
    
                                                
    inventory = db.get_user_inventory(user_id)
    item_in_inventory = None
    for item in inventory:
        if item['item_id'] == item_id and item.get('is_broken', 0) == 0 and item['quantity'] >= quantity:
            item_in_inventory = item
            break
    
    if not item_in_inventory:
        return False, "❌ Недостаточно оборудования в инвентаре или оно не требует починки!", 0.0
    
                              
    item_data = SHOP_ITEMS.get(item_id)
    if not item_data:
        return False, "Предмет не найден", 0.0
    
                                                                 
    if item_data.item_type not in ('gpu', 'asic', 'psu'):
        return False, "❌ Это оборудование не требует починки!", 0.0
    
                                             
    success, repair_cost = db.repair_equipment(user_id, item_id, quantity)
    
    if not success:
        return False, "❌ Не удалось починить оборудование!", 0.0
    
                      
    balance = user.get('balance', 0) or 0
    if balance < repair_cost:
        return False, f"❌ Недостаточно средств! Нужно {repair_cost:.2f} USD, у вас {balance:.2f} USD", repair_cost
    
                      
    db.update_user_balance(user_id, -repair_cost)
    
    return True, f"✅ Оборудование починено! Восстановлено до 100% за {repair_cost:.2f} USD", repair_cost


def scrap_equipment_from_inventory(user_id: int, item_id: str, quantity: int = 1) -> Tuple[bool, str, float]:
    user = db.get_user(user_id)
    if not user:
        return False, "Пользователь не найден", 0.0
    
                                                           
    inventory = db.get_user_inventory(user_id)
    item_in_inventory = None
    for item in inventory:
        if item['item_id'] == item_id and item.get('is_broken', 0) == 1 and item['quantity'] >= quantity:
            item_in_inventory = item
            break
    
    if not item_in_inventory:
        return False, "❌ Недостаточно сломанного оборудования в инвентаре!", 0.0
    
                                                
    success, scrap_value = db.scrap_equipment(user_id, item_id, quantity)
    
    if not success:
        return False, "❌ Не удалось утилизировать оборудование!", 0.0
    
                      
    db.update_user_balance(user_id, scrap_value)
    
    return True, f"✅ Оборудование утилизировано! Получено {scrap_value:.2f} USD", scrap_value

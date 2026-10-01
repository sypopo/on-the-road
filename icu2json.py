import os
import json
import subprocess
import requests
import time
from datetime import datetime
from collections import defaultdict


# =========================================================
# 配置
# =========================================================

API_KEY = os.getenv("ICU_API_KEY", "")
ATHLETE_ID = os.getenv("ICU_ATHLETE_ID", "i692419")

YEAR = int(
    os.getenv(
        "YEAR",
        datetime.now().year
    )
)

OUTPUT_FILE = os.getenv(
    "OUTPUT_FILE",
    "data.json"
)

BASE_URL = "https://intervals.icu/api/v1"

# 最近正式骑行的最低距离
LATEST_RIDE_MIN_KM = float(
    os.getenv(
        "LATEST_RIDE_MIN_KM",
        "10"
    )
)

AUTH = (
    "API_KEY",
    API_KEY
)


# =========================================================
# 触发同步
# =========================================================

def trigger_icu_sync():
    url = f"{BASE_URL}/athlete/{ATHLETE_ID}"

    try:
        print()
        print("正在触发 Intervals.icu 数据同步...")

        r = requests.get(
            url,
            auth=AUTH,
            timeout=30
        )

        if r.status_code == 200:
            print("✅ 数据同步触发成功")
            print("⏳ 等待 3 秒让服务器处理数据...")
            time.sleep(3)
            return True
        else:
            print(f"⚠️ 同步触发返回状态码: {r.status_code}")
            print("继续获取数据...")
            return False

    except Exception as e:
        print(f"⚠️ 同步触发异常: {e}")
        print("继续获取数据...")
        return False


# =========================================================
# API
# =========================================================

def api_get(url, params=None):

    print(f"GET {url}")

    r = requests.get(
        url,
        params=params,
        auth=AUTH,
        timeout=30
    )

    if r.status_code != 200:
        print("API错误:")
        print(r.status_code)
        print(r.text)
        r.raise_for_status()

    return r.json()


# =========================================================
# 日期
# =========================================================

def parse_date(activity):

    date_str = (
        activity.get("start_date_local")
        or activity.get("start_date")
        or activity.get("startTime")
    )

    if not date_str:
        return None

    try:
        return datetime.fromisoformat(
            date_str.replace("Z", "+00:00")
        )
    except Exception:
        return None


# =========================================================
# 距离
# =========================================================

def get_distance_km(activity):

    distance = activity.get("distance")

    if distance is None:
        distance = activity.get("distance_km", 0)

        try:
            return float(distance)
        except Exception:
            return 0

    try:
        return float(distance) / 1000
    except Exception:
        return 0


# =========================================================
# 爬升
# =========================================================

def get_elevation(activity):

    for key in [
        "total_elevation_gain",
        "elevation_gain",
        "elevation"
    ]:
        value = activity.get(key)

        if value is not None:
            try:
                return float(value)
            except Exception:
                pass

    return 0


# =========================================================
# 移动时间
# =========================================================

def get_moving_time(activity):

    for key in [
        "moving_time",
        "moving_time_seconds",
        "elapsed_time"
    ]:
        value = activity.get(key)

        if value is not None:
            try:
                return int(float(value))
            except Exception:
                pass

    return 0


# =========================================================
# 通用数字读取
# =========================================================

def get_number(activity, keys):

    for key in keys:
        value = activity.get(key)

        if value is None:
            continue

        try:
            return float(value)
        except Exception:
            pass

    return None


# =========================================================
# 平均速度
# =========================================================

def get_average_speed_kmh(activity):

    value = get_number(
        activity,
        ["average_speed", "avg_speed"]
    )

    if value is None:
        return None

    return value * 3.6


# =========================================================
# 最大速度
# =========================================================

def get_max_speed_kmh(activity):

    value = get_number(activity, ["max_speed"])

    if value is None:
        return None

    return value * 3.6


# =========================================================
# 平均功率
# =========================================================

def get_average_power(activity):

    return get_number(
        activity,
        ["icu_average_watts", "average_watts"]
    )


# =========================================================
# NP
# =========================================================

def get_normalized_power(activity):

    return get_number(
        activity,
        ["icu_weighted_avg_watts", "weighted_average_watts"]
    )


# =========================================================
# 最大功率
# =========================================================

def get_max_power(activity):

    return get_number(activity, ["max_watts"])


# =========================================================
# 平均心率
# =========================================================

def get_average_hr(activity):

    return get_number(
        activity,
        ["average_heartrate", "average_hr"]
    )


# =========================================================
# 最大心率
# =========================================================

def get_max_hr(activity):

    return get_number(
        activity,
        ["max_heartrate", "max_hr"]
    )


# =========================================================
# 平均步频
# =========================================================

def get_average_cadence(activity):

    value = get_number(
        activity,
        ["average_cadence", "avg_cadence", "average_spm", "avg_spm"]
    )

    # Intervals.icu 返回的是单脚步频，需要乘以 2
    if value is not None:
        return value * 2

    return None


# =========================================================
# 最大步频
# =========================================================

def get_max_cadence(activity):

    value = get_number(
        activity,
        ["max_cadence", "maximum_cadence", "max_spm"]
    )

    if value is not None:
        return value * 2

    return None


# =========================================================
# 平均配速
# =========================================================

def get_average_pace_min_per_km(activity):

    distance_km = get_distance_km(activity)
    moving_seconds = get_moving_time(activity)

    if distance_km <= 0 or moving_seconds <= 0:
        return None

    return (moving_seconds / 60.0) / distance_km


def format_pace(pace_min_per_km):

    if pace_min_per_km is None:
        return None

    total_seconds = round(pace_min_per_km * 60)
    minutes = total_seconds // 60
    seconds = total_seconds % 60

    return f"{minutes}'{seconds:02d}\"/km"


# =========================================================
# 数字格式化
# =========================================================

def clean_number(value, digits=1):

    if value is None:
        return None

    if digits == 0:
        return int(round(value))

    return round(value, digits)


# =========================================================
# 判断运动类型
# =========================================================

def is_ride(activity):

    sport = str(
        activity.get("type")
        or activity.get("sport")
        or activity.get("activity_type")
        or ""
    ).lower()

    return sport in [
        "ride",
        "cycling",
        "bike",
        "virtualride",
        "virtual_ride",
        "ebikeride"
    ]


def is_run(activity):

    sport = str(
        activity.get("type")
        or activity.get("sport")
        or activity.get("activity_type")
        or ""
    ).lower()

    return sport in [
        "run",
        "running",
        "virtualrun"
    ]


# =========================================================
# 获取活动
# =========================================================

def get_activities():

    url = f"{BASE_URL}/athlete/{ATHLETE_ID}/activities"

    oldest = f"{YEAR}-01-01"
    newest = f"{YEAR}-12-31"

    params = {
        "oldest": oldest,
        "newest": newest
    }

    activities = api_get(url, params)

    if not isinstance(activities, list):
        raise RuntimeError("API返回的活动数据不是列表")

    print(f"API获取活动：{len(activities)} 条")

    return activities


# =========================================================
# 活动信息
# =========================================================

def activity_info(activity):

    if not activity:
        return None

    date = parse_date(activity)
    distance_km = get_distance_km(activity)
    moving_time_seconds = get_moving_time(activity)

    average_pace = None
    if distance_km > 0 and moving_time_seconds > 0:
        average_pace = (moving_time_seconds / 60.0) / distance_km

    return {
        "id": activity.get("id"),
        "name": (activity.get("name") or activity.get("title") or "运动"),
        "type": (activity.get("type") or activity.get("sport")),
        "date": (date.strftime("%Y-%m-%d") if date else None),
        "datetime": (date.isoformat() if date else None),
        "distance_km": clean_number(distance_km, 2),
        "moving_time_seconds": moving_time_seconds,
        "elevation_gain_m": clean_number(get_elevation(activity), 1),
        "avg_speed_kmh": clean_number(get_average_speed_kmh(activity), 2),
        "max_speed_kmh": clean_number(get_max_speed_kmh(activity), 2),
        "avg_power_w": clean_number(get_average_power(activity), 0),
        "np_w": clean_number(get_normalized_power(activity), 0),
        "max_power_w": clean_number(get_max_power(activity), 0),
        "avg_hr": clean_number(get_average_hr(activity), 0),
        "max_hr": clean_number(get_max_hr(activity), 0),
        "avg_pace_min_per_km": clean_number(get_average_pace_min_per_km(activity), 2),
        "avg_pace": format_pace(average_pace),
        "avg_cadence": clean_number(get_average_cadence(activity), 1),
        "max_cadence": clean_number(get_max_cadence(activity), 1),
    }


# =========================================================
# 统计
# =========================================================

def build_stats(activities):

    rides = []
    runs = []

    for activity in activities:
        date = parse_date(activity)

        if date is None:
            continue

        if date.year != YEAR:
            continue

        if is_ride(activity):
            rides.append(activity)
        elif is_run(activity):
            runs.append(activity)

    print(f"骑行：{len(rides)}")
    print(f"跑步：{len(runs)}")

    ride_km = sum(get_distance_km(a) for a in rides)
    ride_elevation = sum(get_elevation(a) for a in rides)
    ride_time = sum(get_moving_time(a) for a in rides)

    ride_days = set()
    monthly_ride_days = defaultdict(set)
    monthly_ride_km = defaultdict(float)
    monthly_ride_elevation = defaultdict(float)
    monthly_ride_time = defaultdict(int)

    for activity in rides:
        date = parse_date(activity)
        if not date:
            continue

        month = date.month
        day = date.strftime("%Y-%m-%d")

        ride_days.add(day)
        monthly_ride_days[month].add(day)
        monthly_ride_km[month] += get_distance_km(activity)
        monthly_ride_elevation[month] += get_elevation(activity)
        monthly_ride_time[month] += get_moving_time(activity)

    run_km = sum(get_distance_km(a) for a in runs)
    run_time = sum(get_moving_time(a) for a in runs)

    run_days = set()
    monthly_run_days = defaultdict(set)

    for activity in runs:
        date = parse_date(activity)
        if not date:
            continue

        day = date.strftime("%Y-%m-%d")
        run_days.add(day)
        monthly_run_days[date.month].add(day)

    rides_sorted = sorted(
        rides,
        key=lambda x: parse_date(x) or datetime.min,
        reverse=True
    )

    runs_sorted = sorted(
        runs,
        key=lambda x: parse_date(x) or datetime.min,
        reverse=True
    )

    latest_ride = None
    for activity in rides_sorted:
        if get_distance_km(activity) >= LATEST_RIDE_MIN_KM:
            latest_ride = activity
            break

    if latest_ride is None and rides_sorted:
        latest_ride = rides_sorted[0]

    longest_ride = max(rides, key=get_distance_km, default=None)
    longest_run = max(runs, key=get_distance_km, default=None)

    monthly = []
    for month in range(1, 13):
        monthly.append({
            "month": f"{YEAR}-{month:02d}",
            "ride_km": round(monthly_ride_km[month], 2),
            "elevation_gain_m": round(monthly_ride_elevation[month], 1),
            "ride_days": len(monthly_ride_days[month]),
            "moving_time_seconds": monthly_ride_time[month]
        })

    data = {
        "year": YEAR,
        "ride_km": round(ride_km, 2),
        "moving_time_seconds": ride_time,
        "elevation_gain_meters": round(ride_elevation, 1),
        "ride_days": len(ride_days),
        "monthly_ride_days": [len(monthly_ride_days[i]) for i in range(1, 13)],
        "activity_count": len(rides),
        "monthly": monthly,
        "latest_ride": activity_info(latest_ride),
        "longest_ride": activity_info(longest_ride),
        "run_km": round(run_km, 2),
        "run_moving_time_seconds": run_time,
        "run_days": len(run_days),
        "monthly_run_days": [len(monthly_run_days[i]) for i in range(1, 13)],
        "latest_run": activity_info(runs_sorted[0] if runs_sorted else None),
        "longest_run": activity_info(longest_run),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return data


# =========================================================
# 保存 JSON
# =========================================================

def save_json(data):

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print("data.json 生成成功")
    print("=" * 60)

    print(f"骑行：{data['ride_km']} km")
    print(f"活动数量：{data['activity_count']}")
    print(f"骑行天数：{data['ride_days']}")
    print(f"爬升：{data['elevation_gain_meters']} m")
    print(f"跑步：{data['run_km']} km")
    print(f"跑步天数：{data['run_days']}")
    print(f"更新时间：{data['updated_at']}")

    latest = data.get("latest_ride")
    if latest:
        print()
        print("最近正式骑行：")
        print(f"  名称：{latest['name']}")
        print(f"  日期：{latest['date']}")
        print(f"  距离：{latest['distance_km']} km")
        print(f"  均速：{latest['avg_speed_kmh']} km/h")
        print(f"  最大速度：{latest['max_speed_kmh']} km/h")
        print(f"  平均功率：{latest['avg_power_w']} W")
        print(f"  NP：{latest['np_w']} W")
        print(f"  最大功率：{latest['max_power_w']} W")
        print(f"  平均心率：{latest['avg_hr']} bpm")
        print(f"  最大心率：{latest['max_hr']} bpm")

    latest_run = data.get("latest_run")
    if latest_run:
        print()
        print("最近跑步：")
        print(f"  名称：{latest_run['name']}")
        print(f"  日期：{latest_run['date']}")
        print(f"  距离：{latest_run['distance_km']} km")
        print(f"  平均配速：{latest_run['avg_pace']}")
        print(f"  平均心率：{latest_run['avg_hr']} bpm")

        if latest_run.get("avg_cadence") is not None:
            print(f"  平均步频：{latest_run['avg_cadence']} spm")

        if latest_run.get("max_cadence") is not None:
            print(f"  最大步频：{latest_run['max_cadence']} spm")


# =========================================================
# OSS 上传
# =========================================================

def upload_to_oss():

    oss_key = os.getenv("OSS_KEY", "")
    oss_secret = os.getenv("OSS_SECRET", "")
    oss_endpoint = os.getenv("OSS_ENDPOINT", "")
    oss_bucket = os.getenv("OSS_BUCKET", "")

    missing = []

    if not oss_key:
        missing.append("OSS_KEY")
    if not oss_secret:
        missing.append("OSS_SECRET")
    if not oss_endpoint:
        missing.append("OSS_ENDPOINT")
    if not oss_bucket:
        missing.append("OSS_BUCKET")

    if missing:
        print()
        print("⚠️ OSS配置不完整")
        print("缺少：" + ", ".join(missing))
        return

    try:
        import oss2

        print()
        print("=" * 60)
        print("☁️ 上传到阿里云 OSS")
        print("=" * 60)

        auth = oss2.Auth(oss_key, oss_secret)
        bucket = oss2.Bucket(
            auth,
            f"https://{oss_endpoint}",
            oss_bucket
        )

        print(f"目标：oss://{oss_bucket}/data.json")

        with open(OUTPUT_FILE, "rb") as f:
            bucket.put_object("data.json", f)

        print()
        print("✅ OSS上传成功")

    except ImportError:
        print("⚠️ oss2 未安装，跳过 OSS 上传")
        print("  GitHub Actions 里已安装 oss2")
    except Exception as e:
        print(f"❌ OSS上传失败: {e}")


# =========================================================
# 主程序
# =========================================================

if __name__ == "__main__":

    if not API_KEY:
        raise RuntimeError("请设置 ICU_API_KEY")

    if not ATHLETE_ID:
        raise RuntimeError("请设置 ICU_ATHLETE_ID")

    print()
    print("=" * 60)
    print("Intervals.icu 数据同步")
    print(f"统计年份：{YEAR}")
    print("=" * 60)

    trigger_icu_sync()
    activities = get_activities()
    data = build_stats(activities)
    save_json(data)
    upload_to_oss()

    print()
    print("=" * 60)
    print("🎉 全部完成")
    print("=" * 60)
#!/usr/bin/env python3
"""
Generate a realistic industrial dataset for testing AI agents.
Produces ERP orders, machine cycles, quality checks, maintenance events,
operator notes, and ground truth with 6 known defect scenarios.
"""

import json
import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

SEED = 42
np.random.seed(SEED)
random.seed(SEED)

OUTPUT = "data/scenarios/industrial_demo"
os.makedirs(OUTPUT, exist_ok=True)

MACHINES = {
    "152":  {"name": "Presse 152",  "type": "small"},
    "1003": {"name": "Presse 1003", "type": "medium"},
    "606":  {"name": "Presse 606",  "type": "large"},
}

PRODUCTS_BY_MACHINE = {
    "152": [
        {"ref": "REF-BC-001", "name": "Capuchon bleu",       "cycle_time_s": 22, "cavities": 8,  "weight_g": 12.5},
        {"ref": "REF-CF-002", "name": "Clip de fixation",    "cycle_time_s": 18, "cavities": 12, "weight_g": 8.3},
        {"ref": "REF-BJ-007", "name": "Boîtier joint",       "cycle_time_s": 25, "cavities": 4,  "weight_g": 28.0},
    ],
    "1003": [
        {"ref": "REF-CP-003", "name": "Cache prise",         "cycle_time_s": 32, "cavities": 4,  "weight_g": 45.0},
        {"ref": "REF-SM-004", "name": "Support moteur",      "cycle_time_s": 35, "cavities": 2,  "weight_g": 85.0},
        {"ref": "REF-CR-008", "name": "Connecteur rapide",   "cycle_time_s": 28, "cavities": 8,  "weight_g": 22.0},
        {"ref": "REF-GP-010", "name": "Guide piston",        "cycle_time_s": 30, "cavities": 4,  "weight_g": 38.0},
    ],
    "606": [
        {"ref": "REF-BV-005", "name": "Bouchon vanne",       "cycle_time_s": 42, "cavities": 4,  "weight_g": 65.0},
        {"ref": "REF-PC-006", "name": "Pied caoutchouc",     "cycle_time_s": 38, "cavities": 6,  "weight_g": 52.0},
        {"ref": "REF-CC-009", "name": "Cache culasse",       "cycle_time_s": 45, "cavities": 2,  "weight_g": 120.0},
    ],
}

MATERIALS = [
    {"ref": "MAT-PP-01",  "name": "Polypropylène PP 7520"},
    {"ref": "MAT-PA-02",  "name": "Polyamide PA66 30GF"},
    {"ref": "MAT-ABS-03", "name": "ABS Terluran GP-35"},
    {"ref": "MAT-PE-04",  "name": "Polyéthylène PE 500"},
    {"ref": "MAT-PC-05",  "name": "Polycarbonate Makrolon 2456"},
]

PRODUCT_MATERIAL = {
    "REF-BC-001": "MAT-PP-01", "REF-CF-002": "MAT-PP-01",
    "REF-CP-003": "MAT-ABS-03", "REF-SM-004": "MAT-PA-02",
    "REF-BV-005": "MAT-PA-02", "REF-PC-006": "MAT-PE-04",
    "REF-BJ-007": "MAT-ABS-03", "REF-CR-008": "MAT-PA-02",
    "REF-CC-009": "MAT-PC-05", "REF-GP-010": "MAT-PP-01",
}

TOOLS = {
    "152":  {"A": "MOULE-152-A", "B": "MOULE-152-B"},
    "1003": {"A": "MOULE-1003-A", "B": "MOULE-1003-B"},
    "606":  {"A": "MOULE-606-A", "B": "MOULE-606-B"},
}

NOMINAL_PARAMS = {
    "152": {
        "dosing_time_s": (4.0, 5.0), "injection_time_s": (1.5, 2.5),
        "cooling_time_s": (8.0, 15.0), "cushion_mm": (3.0, 4.5),
        "switchover_position_mm": (10.0, 14.0), "switchover_pressure_bar": (100, 140),
        "peak_pressure_bar": (700, 800), "clamp_force_kn": (550, 650),
        "mold_temperature_c": (40, 50), "barrel_temp_zone1_c": (190, 200),
        "barrel_temp_zone2_c": (205, 215), "barrel_temp_zone3_c": (195, 205),
        "oil_temperature_c": (45, 52), "energy_kwh": (0.3, 0.5),
    },
    "1003": {
        "dosing_time_s": (5.0, 8.0), "injection_time_s": (2.0, 4.0),
        "cooling_time_s": (12.0, 20.0), "cushion_mm": (4.0, 6.0),
        "switchover_position_mm": (15.0, 20.0), "switchover_pressure_bar": (150, 200),
        "peak_pressure_bar": (800, 900), "clamp_force_kn": (1200, 1500),
        "mold_temperature_c": (50, 65), "barrel_temp_zone1_c": (195, 210),
        "barrel_temp_zone2_c": (220, 235), "barrel_temp_zone3_c": (210, 225),
        "oil_temperature_c": (48, 55), "energy_kwh": (0.8, 1.2),
    },
    "606": {
        "dosing_time_s": (6.0, 10.0), "injection_time_s": (3.0, 6.0),
        "cooling_time_s": (18.0, 28.0), "cushion_mm": (5.0, 8.0),
        "switchover_position_mm": (18.0, 25.0), "switchover_pressure_bar": (180, 250),
        "peak_pressure_bar": (900, 1050), "clamp_force_kn": (2500, 3500),
        "mold_temperature_c": (55, 75), "barrel_temp_zone1_c": (210, 225),
        "barrel_temp_zone2_c": (235, 250), "barrel_temp_zone3_c": (225, 240),
        "oil_temperature_c": (50, 58), "energy_kwh": (1.5, 2.5),
    },
}

SHIFTS = [
    {"id": "S1", "number": 1, "start_hour": 6,  "end_hour": 14},
    {"id": "S2", "number": 2, "start_hour": 14, "end_hour": 22},
    {"id": "S3", "number": 3, "start_hour": 22, "end_hour": 6, "crosses_midnight": True},
]


def get_product_by_ref(ref):
    for prods in PRODUCTS_BY_MACHINE.values():
        for p in prods:
            if p["ref"] == ref:
                return p
    return None


def fmt_ts(dt):
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def generate_erp_orders():
    start_date = datetime(2025, 2, 10, 0, 0, 0)
    orders = []
    oid = 1
    for day in range(7):
        d = start_date + timedelta(days=day)
        pb, pm, pl = PRODUCTS_BY_MACHINE["152"], PRODUCTS_BY_MACHINE["1003"], PRODUCTS_BY_MACHINE["606"]
        sched = []
        
        # Machine 152
        sched.append((d, "152", pb[0]["ref"], "A", 5.0, "S1"))
        sched.append((d, "152", pb[1]["ref"], "B", 4.5, "S2"))
        if day < 5:
            sched.append((d, "152", pb[2]["ref"], "A", 6.0, "S3"))
            
        # Machine 1003
        if day % 2 == 0:
            sched.append((d, "1003", pm[3]["ref"], "B", 5.0, "S1"))
        else:
            sched.append((d, "1003", pm[0]["ref"], "A", 5.0, "S1"))
        sched.append((d, "1003", pm[1]["ref"], "B", 6.0, "S2"))
        sched.append((d, "1003", pm[2]["ref"], "A", 4.0, "S3"))
        
        # Machine 606
        sched.append((d, "606", pl[0]["ref"], "A", 6.0, "S1"))
        sched.append((d, "606", pl[1]["ref"], "B", 5.0, "S2"))
        if day < 6:
            sched.append((d, "606", pl[2]["ref"], "A", 7.0, "S3"))
        sh_map = {s["id"]: s["start_hour"] for s in SHIFTS}
        for sd, mac, pref, tkey, dur, sid in sched:
            sh = sh_map[sid]
            so = random.randint(0, 60)
            ost = sd + timedelta(hours=sh, minutes=so)
            oet = ost + timedelta(hours=dur)
            prod = get_product_by_ref(pref)
            tref = TOOLS[mac][tkey]
            mref = PRODUCT_MATERIAL[pref]
            snum = next(s["number"] for s in SHIFTS if s["id"] == sid)
            tqty = int((dur * 3600) / prod["cycle_time_s"] * prod["cavities"] * 0.95)
            orders.append({
                "production_order_id": f"OF-2025-{oid:04d}",
                "machine_erp_ref": mac, "machine_name": MACHINES[mac]["name"],
                "shift_id": sid, "shift_number": snum,
                "started_at": ost, "ended_at": oet,
                "product_ref": pref, "product_name": prod["name"],
                "tool_ref": tref, "material_ref": mref,
                "target_quantity": tqty,
                "theoretical_cycle_time_s": prod["cycle_time_s"],
                "planned_runtime_h": dur,
                "expected_trs": round(random.uniform(0.82, 0.94), 2),
                "expected_scrap_rate": round(random.uniform(0.01, 0.04), 3),
            })
            oid += 1
    df = pd.DataFrame(orders)
    df["started_at"] = pd.to_datetime(df["started_at"])
    df["ended_at"] = pd.to_datetime(df["ended_at"])
    df["machine_erp_ref"] = df["machine_erp_ref"].astype(str)
    return df


def generate_normal_cycle(order, counter, ts, mid):
    prod = get_product_by_ref(order["product_ref"])
    params = NOMINAL_PARAMS[mid]
    ct = max(prod["cycle_time_s"] + random.gauss(0, 0.5), prod["cycle_time_s"] * 0.85)

    def nr(key):
        lo, hi = params[key]
        return random.uniform(lo, hi)
    return {
        "timestamp": ts, "machine_erp_ref": mid,
        "production_order_id": order["production_order_id"],
        "cycle_counter": counter, "cycle_time_s": round(ct, 1),
        "dosing_time_s": round(nr("dosing_time_s") + random.gauss(0, 0.2), 1),
        "injection_time_s": round(nr("injection_time_s") + random.gauss(0, 0.1), 1),
        "cooling_time_s": round(nr("cooling_time_s") + random.gauss(0, 0.3), 1),
        "cushion_mm": round(nr("cushion_mm") + random.gauss(0, 0.1), 1),
        "switchover_position_mm": round(nr("switchover_position_mm") + random.gauss(0, 0.2), 1),
        "switchover_pressure_bar": round(nr("switchover_pressure_bar") + random.gauss(0, 3), 0),
        "peak_pressure_bar": round(nr("peak_pressure_bar") + random.gauss(0, 8), 0),
        "clamp_force_kn": round(nr("clamp_force_kn") + random.gauss(0, 10), 0),
        "mold_temperature_c": round(nr("mold_temperature_c") + random.gauss(0, 0.5), 1),
        "barrel_temp_zone1_c": round(nr("barrel_temp_zone1_c") + random.gauss(0, 0.5), 1),
        "barrel_temp_zone2_c": round(nr("barrel_temp_zone2_c") + random.gauss(0, 0.5), 1),
        "barrel_temp_zone3_c": round(nr("barrel_temp_zone3_c") + random.gauss(0, 0.5), 1),
        "oil_temperature_c": round(nr("oil_temperature_c") + random.gauss(0, 0.3), 1),
        "energy_kwh": round(nr("energy_kwh") + random.gauss(0, 0.02), 3),
        "good_part": True, "scrap_flag": 0, "quality_flag": "good",
    }


def inject_background_noise(cycles, rate=0.015):
    dtypes = ["short_shot", "flash", "sink_mark", "bubbles", "warpage"]
    for i in range(len(cycles)):
        if random.random() < rate:
            cycles[i]["good_part"] = False
            cycles[i]["scrap_flag"] = 1
            cycles[i]["quality_flag"] = random.choice(dtypes)


def inject_missing_values(cycles, rate=0.01):
    fields = [
        "cycle_time_s","dosing_time_s","injection_time_s","cooling_time_s",
        "cushion_mm","switchover_position_mm","switchover_pressure_bar",
        "peak_pressure_bar","mold_temperature_c","barrel_temp_zone1_c",
        "barrel_temp_zone2_c","barrel_temp_zone3_c","oil_temperature_c","energy_kwh"]
    for i in range(len(cycles)):
        if random.random() < rate:
            cycles[i][random.choice(fields)] = None


def inject_s001(cycles, morders):
    to = None
    for _, o in morders.iterrows():
        if o["product_ref"] == "REF-BJ-007" and o["started_at"].day == 11:
            to = o; break
    if to is None: return None
    oid = to["production_order_id"]
    oc = [c for c in cycles if c["production_order_id"] == oid]
    if not oc: return None
    si, ei = len(oc)//3, min(len(oc)//3 + int(1.5*3600/25), len(oc))
    for i in range(si, ei):
        c = oc[i]
        if c["barrel_temp_zone2_c"] is not None:
            c["barrel_temp_zone2_c"] = round(c["barrel_temp_zone2_c"] - random.uniform(12,18), 1)
        if c["injection_time_s"] is not None:
            c["injection_time_s"] = round(c["injection_time_s"]*random.uniform(0.85,0.95), 1)
        if c["peak_pressure_bar"] is not None:
            c["peak_pressure_bar"] = round(c["peak_pressure_bar"]*random.uniform(1.05,1.15), 0)
        prob = 0.15 + 0.35*(i-si)/(ei-si)
        if random.random() < prob:
            c["good_part"]=False; c["scrap_flag"]=1; c["quality_flag"]="short_shot"
    return {
        "scenario_id":"S001","title":"Température trop basse causant des short shots",
        "machine_erp_ref":"152","production_order_id":oid,
        "start_time":fmt_ts(oc[si]["timestamp"]),
        "end_time":fmt_ts(oc[min(ei,len(oc)-1)]["timestamp"]),
        "expected_defect":"short_shot",
        "root_cause":"barrel_temp_zone2_c below nominal range (205-215°C) -> material too viscous -> incomplete cavity fill",
        "evidence_fields":["barrel_temp_zone2_c","quality_flag","scrap_flag","injection_time_s","operator_notes"],
        "expected_agent_conclusion":f"Les short shots sur la machine 152 (OF {oid}) sont probablement lies a une baisse de temperature de la zone 2 du fourreau sous le seuil nominal, rendant la matiere plus visqueuse et empechant le remplissage complet de l'empreinte.",
    }


def inject_s002(cycles, morders):
    to = None
    for _, o in morders.iterrows():
        if o["product_ref"]=="REF-SM-004" and o["started_at"].day==13:
            to=o; break
    if to is None: return None
    oid=to["production_order_id"]
    oc=[c for c in cycles if c["production_order_id"]==oid]
    if not oc: return None
    si,ei=len(oc)//2,min(len(oc)//2+int(3600/35),len(oc))
    for i in range(si,ei):
        c=oc[i]
        if c["peak_pressure_bar"] is not None:
            c["peak_pressure_bar"]=round(c["peak_pressure_bar"]*random.uniform(1.12,1.25),0)
        if c["switchover_pressure_bar"] is not None:
            c["switchover_pressure_bar"]=round(c["switchover_pressure_bar"]*random.uniform(1.1,1.2),0)
        if c["clamp_force_kn"] is not None:
            c["clamp_force_kn"]=round(c["clamp_force_kn"]*random.uniform(0.92,0.98),0)
        prob=0.2+0.3*(i-si)/(ei-si)
        if random.random()<prob:
            c["good_part"]=False;c["scrap_flag"]=1;c["quality_flag"]="flash"
    return {
        "scenario_id":"S002","title":"Pression injection trop elevee causant des bavures (flash)",
        "machine_erp_ref":"1003","production_order_id":oid,
        "start_time":fmt_ts(oc[si]["timestamp"]),
        "end_time":fmt_ts(oc[min(ei,len(oc)-1)]["timestamp"]),
        "expected_defect":"flash",
        "root_cause":"peak_pressure_bar above nominal (800-900 bar) combined with reduced clamp_force_kn -> mould separates -> flash formation",
        "evidence_fields":["peak_pressure_bar","switchover_pressure_bar","clamp_force_kn","quality_flag","scrap_flag"],
        "expected_agent_conclusion":"Les bavures (flash) sur la machine 1003 sont causees par une pression d'injection trop elevee associee a un effort de verrouillage insuffisant, permettant a la matiere de s'echapper entre les plans de joint.",
    }


def inject_s003(cycles, morders):
    to=None
    for _,o in morders.iterrows():
        if o["product_ref"]=="REF-CC-009" and o["started_at"].day==14:
            to=o;break
    if to is None: return None
    oid=to["production_order_id"]
    oc=[c for c in cycles if c["production_order_id"]==oid]
    if not oc: return None
    si,ei=len(oc)//2,min(len(oc)//2+int(2*3600/45),len(oc))
    for i in range(si,ei):
        c=oc[i]
        if c["cooling_time_s"] is not None:
            c["cooling_time_s"]=round(max(c["cooling_time_s"]+np.sin((i-si)*0.3)*8,10),1)
        if c["mold_temperature_c"] is not None:
            c["mold_temperature_c"]=round(c["mold_temperature_c"]+random.uniform(-6,6),1)
        if c["energy_kwh"] is not None:
            c["energy_kwh"]=round(c["energy_kwh"]*random.uniform(1.05,1.15),3)
        prob=0.15+0.25*(i-si)/(ei-si)
        if random.random()<prob:
            c["good_part"]=False;c["scrap_flag"]=1;c["quality_flag"]="warpage"
    return {
        "scenario_id":"S003","title":"Refroidissement instable causant des deformations (warpage)",
        "machine_erp_ref":"606","production_order_id":oid,
        "start_time":fmt_ts(oc[si]["timestamp"]),
        "end_time":fmt_ts(oc[min(ei,len(oc)-1)]["timestamp"]),
        "expected_defect":"warpage",
        "root_cause":"cooling_time_s and mold_temperature_c oscillating -> uneven cooling -> internal stresses -> warpage",
        "evidence_fields":["cooling_time_s","mold_temperature_c","quality_flag","scrap_flag","energy_kwh"],
        "expected_agent_conclusion":"Les deformations (warpage) sont liees a une instabilite du refroidissement: le temps de refroidissement et la temperature du moule varient de maniere cyclique, creant des contraintes internes dans la piece.",
    }


def inject_s004(cycles, morders):
    ol=list(morders.iterrows())
    mci=None
    for idx in range(1,len(ol)):
        _,p=ol[idx-1]; _,c=ol[idx]
        if p["material_ref"]!=c["material_ref"] and c["started_at"].day==11:
            mci=idx;break
    if mci is None: return None
    _,co=ol[mci]; oid=co["production_order_id"]
    oc=[c for c in cycles if c["production_order_id"]==oid]
    if not oc: return None
    ei=min(int(1.5*3600/30),len(oc))
    for i in range(ei):
        prob=0.2*(1-i/ei)+0.05
        if random.random()<prob:
            oc[i]["good_part"]=False;oc[i]["scrap_flag"]=1;oc[i]["quality_flag"]="bubbles"
    return {
        "scenario_id":"S004","title":"Changement matiere provoquant des bulles",
        "machine_erp_ref":"1003","production_order_id":oid,
        "start_time":fmt_ts(oc[0]["timestamp"]),
        "end_time":fmt_ts(oc[min(ei-1,len(oc)-1)]["timestamp"]),
        "expected_defect":"bubbles",
        "root_cause":"Material change without proper purging -> residual moisture or incompatible materials -> gas formation -> bubbles",
        "evidence_fields":["quality_flag","scrap_flag","maintenance_events","operator_notes"],
        "expected_agent_conclusion":"Les bulles observees juste apres le changement de matiere sont probablement dues a une purge insuffisante ou a un sechage inadequate de la nouvelle matiere, emprisonnant des gaz dans la cavite.",
    }


def inject_s005(cycles, morders):
    to=None
    for _,o in morders.iterrows():
        if o["product_ref"]=="REF-CF-002" and o["started_at"].day==12:
            to=o;break
    if to is None: return None
    oid=to["production_order_id"]
    oc=[c for c in cycles if c["production_order_id"]==oid]
    if not oc: return None
    ei=min(int(0.5*3600/18),len(oc))
    for i in range(ei):
        c=oc[i]
        prob=0.5*(1-i/ei)+0.1
        if random.random()<prob:
            c["good_part"]=False;c["scrap_flag"]=1
            c["quality_flag"]=random.choice(["short_shot","flash","sink_mark"])
        if c["barrel_temp_zone1_c"] is not None:
            c["barrel_temp_zone1_c"]=round(c["barrel_temp_zone1_c"]-random.uniform(3,8),1)
        if c["barrel_temp_zone2_c"] is not None:
            c["barrel_temp_zone2_c"]=round(c["barrel_temp_zone2_c"]-random.uniform(3,8),1)
    return {
        "scenario_id":"S005","title":"Redemarrage machine causant un rebut temporaire",
        "machine_erp_ref":"152","production_order_id":oid,
        "start_time":fmt_ts(oc[0]["timestamp"]),
        "end_time":fmt_ts(oc[min(ei-1,len(oc)-1)]["timestamp"]),
        "expected_defect":"multiple (short_shot, flash, sink_mark)",
        "root_cause":"Machine restart after stop -> thermal instability -> parameter deviation -> high defect rate until steady state",
        "evidence_fields":["quality_flag","scrap_flag","barrel_temp_zone1_c","barrel_temp_zone2_c","maintenance_events","operator_notes"],
        "expected_agent_conclusion":"Le taux de rebut eleve en debut d'OF est du a un redemarrage de la machine apres un arret. Les temperatures fourreau ne sont pas stabilisees, provoquant des defauts varies le temps que le regime thermique s'etablisse.",
    }


def inject_s006(cycles, morders):
    ta_ords=[]
    for _,o in morders.iterrows():
        if str(o["machine_erp_ref"])=="606" and "A" in str(o["tool_ref"]) and o["started_at"].day>=14:
            ta_ords.append(o)
    if not ta_ords: return None
    fo=ta_ords[0]; lo=ta_ords[-1]
    return {
        "scenario_id":"S006","title":"Usure progressive du moule causant une derive dimensionnelle",
        "machine_erp_ref":"606",
        "production_order_id":f"{fo['production_order_id']} to {lo['production_order_id']}",
        "start_time":fmt_ts(fo["started_at"]),
        "end_time":fmt_ts(lo["ended_at"]),
        "expected_defect":"dimension_out_of_tolerance",
        "root_cause":"Progressive mold wear on MOULE-606-A -> cavity dimensions increase -> part dimensions drift -> out-of-tolerance",
        "evidence_fields":["dimension_deviation_mm","measured_weight_g","quality_flag","operator_notes"],
        "expected_agent_conclusion":"La derive dimensionnelle observee sur les pieces produites par le moule MOULE-606-A est coherente avec une usure progressive de l'outillage. Les cotes augmentent lentement au fil des OF, depassant finalement les tolerances.",
    }


def generate_machine_cycles(mid, orders_df):
    mords = orders_df[orders_df["machine_erp_ref"].astype(str)==mid].sort_values("started_at")
    all_cycles = []
    for _, order in mords.iterrows():
        ct = order["started_at"]
        cnt = 1
        while ct < order["ended_at"]:
            cyc = generate_normal_cycle(order.to_dict(), cnt, ct, mid)
            all_cycles.append(cyc)
            ct += timedelta(seconds=max(cyc["cycle_time_s"]+random.uniform(-0.5,1.0), 10))
            cnt += 1

    inject_background_noise(all_cycles, 0.015)
    inject_missing_values(all_cycles, 0.01)

    s_injectors = {
        "152": [inject_s001, inject_s005],
        "1003": [inject_s002, inject_s004],
        "606": [inject_s003, inject_s006],
    }
    sinfo = []
    for fn in s_injectors.get(mid, []):
        r = fn(all_cycles, mords)
        if r:
            sinfo.append(r)

    return pd.DataFrame(all_cycles), sinfo


def generate_quality_checks(all_mc, orders_df):
    checks = []
    cid = 1
    for _, order in orders_df.iterrows():
        mid = str(order["machine_erp_ref"])
        mc = all_mc.get(mid, pd.DataFrame())
        if mc.empty: continue
        oc = mc[mc["production_order_id"]==order["production_order_id"]].sort_values("timestamp")
        if oc.empty: continue

        interval = timedelta(minutes=random.randint(30, 60))
        ct = order["started_at"]
        while ct < order["ended_at"]:
            ws = ct - interval
            wc = oc[(oc["timestamp"]>=ws)&(oc["timestamp"]<ct)]
            if not wc.empty:
                ss = min(random.randint(8,20), len(wc))
                sample = wc.sample(n=ss)
                defects = sample[sample["scrap_flag"]==1]
                nd = len(defects)
                dt_list = [x for x in defects["quality_flag"].dropna().unique() if x!="good"]
                prod = get_product_by_ref(order["product_ref"])
                tw = prod["weight_g"] if prod else 50.0
                mw = round(tw+random.gauss(0,0.3),1)

                # dimensional drift for S006 (progressive mold wear)
                dim_dev = round(random.gauss(0,0.05),3)
                if mid=="606" and "A" in str(order.get("tool_ref","")):
                    if ct >= datetime(2025, 2, 14):
                        frac = (ct - datetime(2025, 2, 14)).total_seconds() / (3 * 24 * 3600)
                        frac = max(0, min(1, frac))
                        dim_dev = round(frac * 0.7 + random.gauss(0, 0.04), 3)
                        dim_dev = max(0, dim_dev)

                if nd==0: sev, vis="none","ok"
                elif nd<=2: sev, vis="minor","minor_defects"
                elif nd<=5: sev, vis="moderate","defective"
                else: sev, vis="critical","defective"

                cmt = ""
                if len(dt_list)==1: cmt=f"Presence de {dt_list[0]}"
                elif len(dt_list)>1: cmt=f"Defauts multiples: {', '.join(dt_list)}"
                elif nd>0: cmt=f"{nd} pieces non conformes"
                else: cmt="Conforme" if random.random()>0.3 else ""

                checks.append({
                    "quality_check_id":f"QC-{cid:04d}",
                    "timestamp":ct, "production_order_id":order["production_order_id"],
                    "machine_erp_ref":mid, "product_ref":order["product_ref"],
                    "sample_size":ss, "defect_count":nd,
                    "defect_type":",".join(dt_list) if dt_list else "",
                    "severity":sev, "measured_weight_g":mw,
                    "target_weight_g":tw, "dimension_deviation_mm":dim_dev,
                    "visual_result":vis, "comment":cmt,
                })
                cid+=1
            ct+=interval
    return pd.DataFrame(checks)


def _find_order_at(orders_df, machine_erp_ref, timestamp):
    orders = orders_df[orders_df["machine_erp_ref"].astype(str) == str(machine_erp_ref)].copy()
    for _, o in orders.iterrows():
        if o["started_at"] <= timestamp <= o["ended_at"]:
            return o["production_order_id"]
    if orders.empty:
        return ""
    # No exact match: return the nearest order by time
    orders["_tdiff"] = abs(orders["started_at"] - pd.Timestamp(timestamp))
    return orders.sort_values("_tdiff").iloc[0]["production_order_id"]


def generate_maintenance_events(orders_df, scenario_info):
    events=[]
    eid=1
    # Generic preventive maintenance (noise, no scenario link)
    for day in [2,5]:
        for mid in ["152","1003","606"]:
            events.append({
                "event_id":f"MAINT-{eid:04d}",
                "timestamp":datetime(2025,2,10+day,8,0,0),
                "machine_erp_ref":mid, "production_order_id":"",
                "event_type":"maintenance preventive",
                "duration_min":random.randint(60,120),"severity":"low",
                "description":f"Maintenance preventive programmee - {MACHINES[mid]['name']}",
            }); eid+=1
    # Generic mold cleaning (noise)
    for mid,day in [("152",3),("1003",4),("606",5)]:
        events.append({
            "event_id":f"MAINT-{eid:04d}",
            "timestamp":datetime(2025,2,10+day,12,0,0),
            "machine_erp_ref":mid,"production_order_id":"",
            "event_type":"nettoyage moule","duration_min":random.randint(20,45),"severity":"low",
            "description":f"Nettoyage moule {MACHINES[mid]['name']}",
        }); eid+=1
    # Scenario-driven events — placed precisely in each scenario's ±2h window
    for s in scenario_info:
        if s is None: continue
        ev = s.get("evidence_fields", [])
        if "maintenance_events" not in ev: continue
        sid, mid = s["scenario_id"], s["machine_erp_ref"]
        st = datetime.fromisoformat(s["start_time"])
        et = datetime.fromisoformat(s["end_time"])
        win_s, win_e = st - timedelta(hours=2), et + timedelta(hours=2)
        if sid == "S004":
            ts = st - timedelta(minutes=random.randint(10, 60))
            if ts < win_s: ts = win_s + timedelta(minutes=random.randint(1, 30))
            events.append({
                "event_id":f"MAINT-{eid:04d}","timestamp":ts,
                "machine_erp_ref":mid,
                "production_order_id":_find_order_at(orders_df,mid,ts),
                "event_type":"changement matiere","duration_min":45,"severity":"medium",
                "description":f"Changement matiere sur presse {mid} suite au scenario {sid}",
            }); eid+=1
        elif sid == "S005":
            ts_stop = st - timedelta(hours=random.uniform(1, 2.5))
            if ts_stop < win_s: ts_stop = win_s + timedelta(minutes=random.randint(1, 15))
            events.append({
                "event_id":f"MAINT-{eid:04d}","timestamp":ts_stop,
                "machine_erp_ref":mid,"production_order_id":"",
                "event_type":"arret machine","duration_min":120,"severity":"medium",
                "description":f"Arret machine {mid} pour maintenance",
            }); eid+=1
            ts_rest = st - timedelta(minutes=random.randint(5, 30))
            if ts_rest < ts_stop: ts_rest = ts_stop + timedelta(minutes=random.randint(60, 90))
            events.append({
                "event_id":f"MAINT-{eid:04d}","timestamp":ts_rest,
                "machine_erp_ref":mid,
                "production_order_id":_find_order_at(orders_df,mid,ts_rest),
                "event_type":"redemarrage","duration_min":15,"severity":"medium",
                "description":f"Redemarrage machine {mid} apres maintenance",
            }); eid+=1
    return pd.DataFrame(events)

def generate_operator_notes(events, scenario_info, orders_df):
    """Generate operator notes from scenario windows + noise."""
    notes=[]; nid=1

    def _find_oid(ts, mid):
        o = orders_df[(orders_df["machine_erp_ref"].astype(str)==mid)&(orders_df["started_at"]<=ts)&(orders_df["ended_at"]>=ts)]
        if len(o):
            return o["production_order_id"].iloc[0]
        o2 = orders_df[orders_df["machine_erp_ref"].astype(str)==mid].copy()
        if len(o2):
            o2["_td"] = abs(o2["started_at"] - pd.Timestamp(ts))
            return o2.sort_values("_td").iloc[0]["production_order_id"]
        return ""

    def add(ts, mid, op, txt):
        nonlocal nid
        oid = _find_oid(ts, mid)
        notes.append({
            "note_id":f"NOTE-{nid:04d}","timestamp":ts,
            "machine_erp_ref":mid,"production_order_id":oid,
            "operator_id":op,"note_text":txt,
        }); nid+=1

    # ── Scenario-driven notes ──
    note_templates = {
        "S001": [
            ("Temperature matiere instable depuis changement lot. Plusieurs short shots constates.",
             "OP-042"),
            ("Zone 2 affiche des temperatures sous le seuil nominal. Verifier resistance chauffante.",
             "OP-042"),
        ],
        "S004": [
            ("Bulles dans les pieces apres changement matiere. Verifier sechage granules.",
             "OP-037"),
        ],
        "S005": [
            ("Plusieurs pieces avec bavures et short shots apres redemarrage. Temperatures pas stables.",
             "OP-042"),
        ],
        "S006": [
            ("Cotes des pieces augmentent anormalement. Moule commence a montrer des signes d'usure.",
             "OP-051"),
            ("Moule nettoye mais derive dimensionnelle toujours presente. Sera a surveiller.",
             "OP-051"),
        ],
    }
    for s in scenario_info:
        if s is None: continue
        ev = s.get("evidence_fields", [])
        if "operator_notes" not in ev: continue
        sid, mid = s["scenario_id"], s["machine_erp_ref"]
        st = datetime.fromisoformat(s["start_time"])
        et = datetime.fromisoformat(s["end_time"])
        win_s, win_e = st - timedelta(hours=2), et + timedelta(hours=2)
        templates = note_templates.get(sid, [])
        for txt, op in templates:
            offset = random.uniform(0, (win_e - win_s).total_seconds())
            ts = win_s + timedelta(seconds=offset)
            add(ts, mid, op, txt)

    # ── Ambiguous note (noise, not scenario-linked) ──
    ts = datetime(2025,2,14,8,0,0)
    add(ts, "1003", "OP-037",
        "Defauts intermittents. Cause possible: matiere ou parametres.")

    # ── Pure noise notes ──
    for _ in range(3):
        day=random.randint(0,6); hr=random.randint(8,20); mid=random.choice(["152","1003","606"])
        add(datetime(2025,2,10+day,hr,random.randint(0,59)),mid,f"OP-{random.randint(30,60):03d}",
            random.choice([
                "Production nominale. Aucun probleme signale.",
                "Controle qualite effectue, tout est conforme.",
                "Nettoyage zone de travail effectue.",
                "Releve de temperature OK.",
                "Parametres stables. Bonne journee.",
            ]))
    return pd.DataFrame(notes)


def write_ground_truth(scenarios):
    valid=[s for s in scenarios if s is not None]
    with open(f"{OUTPUT}/ground_truth.json","w") as f:
        json.dump(valid,f,indent=2,ensure_ascii=False,default=str)
    print(f"Ground truth: {len(valid)} scenarios")


def write_readme(n_orders, n_cycles_total, n_quality, n_maint, n_notes, n_scenarios):
    readme=f"""# Industrial Demo Dataset

Dataset industriel fictif pour tester un agent capable de correler donnees ERP, cycles machine, qualite, defauts et causes probables.

## Fichiers

| Fichier | Description |
|---------|-------------|
| `erp_orders.xlsx` | Ordres de fabrication (ERP) |
| `machine_cycles_152.csv` | Cycles machine - Presse 152 (petite) |
| `machine_cycles_1003.csv` | Cycles machine - Presse 1003 (moyenne) |
| `machine_cycles_606.csv` | Cycles machine - Presse 606 (grande) |
| `quality_checks.csv` | Controles qualite |
| `maintenance_events.csv` | Evenements maintenance |
| `operator_notes.csv` | Notes operateur |
| `ground_truth.json` | Verite terrain ({n_scenarios} scenarios de defauts) |

## Schema de correlation

- `production_order_id` -> relie ERP, cycles, qualite et notes
- `machine_erp_ref` -> relie ERP, cycles, maintenance et notes
- `timestamp` -> correlation temporelle entre toutes les sources
- `product_ref` -> relie ERP et qualite
- `tool_ref` -> relie ERP a l'outillage

## Scenarios de defauts

| ID | Machine | Defaut | Cause |
|----|---------|--------|-------|
| S001 | 152 | short_shot | Temperature zone 2 trop basse |
| S002 | 1003 | flash | Pression injection trop elevee |
| S003 | 606 | warpage | Refroidissement instable |
| S004 | 1003 | bubbles | Changement matiere sans purge |
| S005 | 152 | multiple | Redemarrage apres arret |
| S006 | 606 | dimension_out_of_tolerance | Usure progressive du moule |

## Statistiques

- Periode : 7 jours (10-16 fevrier 2025)
- 3 machines d'injection plastique (152, 1003, 606)
- {n_orders} ordres de fabrication
- {n_cycles_total} cycles machine
- {n_quality} controles qualite
- {n_maint} evenements maintenance
- {n_notes} notes operateur
- {n_scenarios} scenarios de defauts injectes
- Donnees imparfaites : valeurs manquantes, bruit, ambiguites
"""
    with open(f"{OUTPUT}/README.md","w") as f:
        f.write(readme)
    print("README.md written.")


def main():
    print("="*60)
    print("Generation du dataset industriel de demonstration")
    print("="*60)

    print("\n[1/7] Generation des ordres ERP...")
    orders_df=generate_erp_orders()
    print(f"  -> {len(orders_df)} ordres generes")

    print("\n[2/7] Generation des cycles machine...")
    all_mc={}; all_s=[]
    for mid in ["152","1003","606"]:
        cdf,si=generate_machine_cycles(mid,orders_df)
        all_mc[mid]=cdf; all_s.extend(si)
        print(f"  -> Machine {mid}: {len(cdf)} cycles, {len(si)} scenario(s)")

    print("\n[3/7] Generation des controles qualite...")
    qdf=generate_quality_checks(all_mc,orders_df)
    print(f"  -> {len(qdf)} controles generes")

    print("\n[4/7] Generation des evenements maintenance...")
    mdf=generate_maintenance_events(orders_df,all_s)
    print(f"  -> {len(mdf)} evenements generes")

    print("\n[5/7] Generation des notes operateur...")
    ndf=generate_operator_notes(mdf,all_s,orders_df)
    print(f"  -> {len(ndf)} notes generees")

    print("\n[6/7] Sauvegarde des fichiers...")
    orders_df["machine_erp_ref"] = orders_df["machine_erp_ref"].astype(str)
    orders_df.to_excel(f"{OUTPUT}/erp_orders.xlsx",index=False); print("  -> erp_orders.xlsx")
    for mid in ["152","1003","606"]:
        all_mc[mid]["machine_erp_ref"] = all_mc[mid]["machine_erp_ref"].astype(str)
        all_mc[mid].to_csv(f"{OUTPUT}/machine_cycles_{mid}.csv",index=False)
        print(f"  -> machine_cycles_{mid}.csv")
    qdf["machine_erp_ref"] = qdf["machine_erp_ref"].astype(str)
    qdf.to_csv(f"{OUTPUT}/quality_checks.csv",index=False); print("  -> quality_checks.csv")
    mdf["machine_erp_ref"] = mdf["machine_erp_ref"].astype(str)
    mdf.to_csv(f"{OUTPUT}/maintenance_events.csv",index=False); print("  -> maintenance_events.csv")
    ndf["machine_erp_ref"] = ndf["machine_erp_ref"].astype(str)
    ndf.to_csv(f"{OUTPUT}/operator_notes.csv",index=False); print("  -> operator_notes.csv")

    print("\n[7/7] Ecriture de la verite terrain et du README...")
    write_ground_truth(all_s)
    total_cycles = sum(len(df) for df in all_mc.values())
    write_readme(len(orders_df), total_cycles, len(qdf), len(mdf), len(ndf), len([s for s in all_s if s]))

    print("\n[7b/7] Validation des contraintes de coherence du dataset...")
    # 1. Pas de chevauchement d'OF sur une même machine
    for mid in ["152", "1003", "606"]:
        m_orders = orders_df[orders_df["machine_erp_ref"].astype(str) == mid].sort_values("started_at")
        prev_end = None
        for _, row in m_orders.iterrows():
            if prev_end and row["started_at"] < prev_end:
                raise AssertionError(f"Machine {mid} has overlapping orders: end of previous was {prev_end}, start of next is {row['started_at']}")
            prev_end = row["ended_at"]
    print("  ✅ Pas de chevauchement d'OF sur une même machine")

    # 2. defect_count <= sample_size
    bad_qcs = qdf[qdf["defect_count"] > qdf["sample_size"]]
    if not bad_qcs.empty:
        raise AssertionError(f"Found {len(bad_qcs)} QCs where defect_count > sample_size")
    print("  ✅ defect_count <= sample_size pour tous les contrôles qualité")

    # 3. Validation des horaires de postes S1/S2/S3
    for _, row in orders_df.iterrows():
        s_id = row["shift_id"]
        start_time = row["started_at"]
        expected_hour = {"S1": 6, "S2": 14, "S3": 22}[s_id]
        if start_time.hour != expected_hour:
            raise AssertionError(f"Order {row['production_order_id']} shift {s_id} started at {start_time.hour}h instead of {expected_hour}h")
    print("  ✅ Les horaires de poste sont corrects (pas de décalage de 6h)")

    print("\n"+"="*60)
    print("Dataset genere avec succes dans data/scenarios/industrial_demo/")
    print("="*60)


if __name__=="__main__":
    main()

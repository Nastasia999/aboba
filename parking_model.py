"""
parking_model.py

Iterative parking allocation model with competition + OD matrix creation from a road graph.

This module now serves as a *facade* over the internal OOP modules:

- `parking_model_pkg.probability` – функция вероятности ходьбы `p_walk_piecewise`
- `parking_model_pkg.parking_config` – конфигурации `GraphBuildConfig`, `ModelConfig`
- `parking_model_pkg.parking_core` – ядро модели `ParkingAccessibilityModel`
- `parking_model_pkg.parking_project` – высокоуровневый класс `ParkingProject` и функция `run_from_files`
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from parking_model_pkg import (
    GraphBuildConfig,
    ModelConfig,
    ParkingAccessibilityModel,
    ParkingProject,
    create_all_visualizations,
    p_walk_exponential,
    p_walk_piecewise,
    plot_coverage_distribution,
    plot_od_flows,
    plot_origin_coverage_map,
    plot_parking_load_distribution,
    plot_parking_load_map,
    run_from_files,
)

__all__ = [
    "p_walk_piecewise",
    "p_walk_exponential",
    "GraphBuildConfig",
    "ModelConfig",
    "ParkingAccessibilityModel",
    "ParkingProject",
    "run_from_files",
    "plot_parking_load_map",
    "plot_origin_coverage_map",
    "plot_parking_load_distribution",
    "plot_coverage_distribution",
    "plot_od_flows",
    "create_all_visualizations",
]


def compute_center_bound_stats(
    results_gpkg_path: str,
    parks_layer: str,
    origins_layer: str | None,
    demand_column: str | None,
    center_bound_path: str,
    center_bound_layer: str,
    output_dir: "Path",
    scenario_type: str,
    paid_parking_enabled: bool,
    workers_release_rate: float,
) -> None:
    """
    Обрезает парковки по границе center_bound и сохраняет сводную статистику в Excel.
    """
    import geopandas as gpd
    import pandas as pd
    from pathlib import Path

    results_path = Path(results_gpkg_path)
    if not results_path.exists():
        logger.warning("Results GeoPackage not found for stats: %s", results_gpkg_path)
        return

    cb_path = Path(center_bound_path)
    if not cb_path.exists():
        logger.warning("Center bound file not found, skipping stats: %s", center_bound_path)
        return

    logger.info(
        "Computing center-bound stats from results=%s, layer=%s, center_bound=%s (layer=%s)",
        results_gpkg_path,
        parks_layer,
        center_bound_path,
        center_bound_layer,
    )

    parks = gpd.read_file(results_gpkg_path, layer=parks_layer)
    center_bound = gpd.read_file(center_bound_path, layer=center_bound_layer)

    if parks.empty:
        logger.warning("No parks loaded from results, skipping stats.")
        return
    if center_bound.empty:
        logger.warning("Center bound layer is empty, skipping stats.")
        return

    if parks.crs != center_bound.crs:
        center_bound = center_bound.to_crs(parks.crs)

    bound_geom = center_bound.unary_union
    parks_in_center = parks[parks.geometry.within(bound_geom)]

    if parks_in_center.empty:
        logger.warning("No parks fall inside center_bound, skipping stats export.")
        return

    # Сводная статистика по основным полям (только внутри центра)
    stats: dict[str, float] = {
        "n_parks_center": float(len(parks_in_center)),
    }
    for col in ["capacity_init", "used", "capacity_rem", "park_load"]:
        if col in parks_in_center.columns:
            s_center = parks_in_center[col].astype(float)
            stats.update(
                {
                    f"{col}_center_sum": float(s_center.sum()),
                    f"{col}_center_mean": float(s_center.mean()),
                    f"{col}_center_median": float(s_center.median()),
                    f"{col}_center_min": float(s_center.min()),
                    f"{col}_center_max": float(s_center.max()),
                }
            )

    # Глобальные суммы по всем парковкам (для проверки спрос/ёмкость по городу)
    for col in ["capacity_init", "used", "capacity_rem", "park_load"]:
        if col in parks.columns:
            s_all = parks[col].astype(float)
            stats.update(
                {
                    f"{col}_all_sum": float(s_all.sum()),
                    f"{col}_all_mean": float(s_all.mean()),
                }
            )

    # Глобальный спрос по выбранной категории (если есть слой origins_result и колонка спроса)
    if origins_layer and demand_column:
        try:
            origins_res = gpd.read_file(results_gpkg_path, layer=origins_layer)
            if demand_column in origins_res.columns:
                d_all = origins_res[demand_column].astype(float)
                demand_total = float(d_all.sum())
                stats["demand_column"] = demand_column
                stats["demand_total_all_origins"] = demand_total

                cap_init_all = stats.get("capacity_init_all_sum")
                if cap_init_all and cap_init_all > 0:
                    stats["demand_to_capacity_init_all_ratio"] = demand_total / cap_init_all
            else:
                logger.warning(
                    "Demand column '%s' not found in origins layer '%s' when computing stats.",
                    demand_column,
                    origins_layer,
                )
        except Exception as exc:  # pragma: no cover - защитное логирование
            logger.warning("Failed to read origins layer '%s' for stats: %s", origins_layer, exc)

    # Информация о сценарии для имени файла и таблицы
    if scenario_type == "projected" and paid_parking_enabled:
        scenario_slug = f"projected_paid_{int(workers_release_rate * 100)}"
        scenario_label = f"Проектное решение: платные парковки (освобождение {int(workers_release_rate * 100)}%)"
    elif scenario_type == "projected":
        scenario_slug = "projected"
        scenario_label = "Проектное решение"
    else:
        scenario_slug = "existing"
        scenario_label = "Существующее положение"

    stats["scenario"] = scenario_label

    summary_df = pd.DataFrame([stats])
    # Таблица по отдельным парковкам (без геометрии)
    detail_df = parks_in_center.drop(columns="geometry", errors="ignore")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    xlsx_path = output_dir / f"parking_center_stats_{scenario_slug}.xlsx"
    logger.info("Saving center-bound stats to Excel: %s", xlsx_path)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="summary")
        detail_df.to_excel(writer, index=False, sheet_name="parks_in_center")

    logger.info("Center-bound stats successfully saved.")


def export_stage_occupancy_stats(
    stage_outputs: dict[str, str],
    stage_demands: dict[str, str],
    parks_layer: str,
    origins_layer: str,
    output_dir: "Path",
    scenario_type: str,
    paid_parking_enabled: bool,
    workers_release_rate: float,
) -> None:
    """
    Экспортирует в Excel долю парковок, занятых населением, рабочими и посетителями
    (до и после «освобождения» части занятых мест).
    """
    import geopandas as gpd
    import pandas as pd
    from pathlib import Path

    if not stage_outputs:
        logger.warning("No stage outputs provided for occupancy stats export.")
        return

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, float | str]] = []

    for stage_name, gpkg_path in stage_outputs.items():
        gpkg_path = Path(gpkg_path)
        if not gpkg_path.exists():
            logger.warning(
                "Stage results file not found for occupancy stats (stage=%s): %s",
                stage_name,
                gpkg_path,
            )
            continue

        logger.info(
            "Computing occupancy stats for stage '%s' from %s (layer=%s)",
            stage_name,
            gpkg_path,
            parks_layer,
        )
        parks = gpd.read_file(gpkg_path, layer=parks_layer)
        if parks.empty:
            logger.warning("No parks in results for stage '%s', skipping.", stage_name)
            continue

        if "capacity_init" not in parks.columns or "used" not in parks.columns:
            logger.warning(
                "Stage '%s' results lack required columns ('capacity_init', 'used'), skipping.",
                stage_name,
            )
            continue

        cap_init = parks["capacity_init"].astype(float)
        used = parks["used"].astype(float)
        cap_sum = float(cap_init.sum())
        used_sum = float(used.sum())

        if cap_sum <= 0:
            logger.warning(
                "Total capacity_init for stage '%s' is non-positive, skipping.", stage_name
            )
            continue

        share_before = used_sum / cap_sum

        # Логика "после вычитания" должна совпадать с тем, как мы обновляем емкость между этапами
        if stage_name == "naselenie":
            # после населения остаётся только 6% ранее занятых мест
            used_after = used_sum * 0.06
        elif (
            stage_name == "workers"
            and scenario_type == "projected"
            and paid_parking_enabled
        ):
            # при проектном сценарии и платных парковках освобождаем workers_release_rate занятых мест
            # т.е. остается (1 - workers_release_rate) от исходной занятости
            used_after = used_sum * (1.0 - workers_release_rate)
        else:
            # для существующего сценария для рабочих и для посетителей "после" = "до"
            used_after = used_sum

        share_after = used_after / cap_sum

        rec: dict[str, float | str] = {
            "stage": stage_name,
            "capacity_init_sum": cap_sum,
            "used_sum_before": used_sum,
            "used_share_before": share_before,
            "used_sum_after": used_after,
            "used_share_after": share_after,
        }

        # Добавляем суммарный спрос D по этому этапу (если знаем колонку)
        demand_col = stage_demands.get(stage_name)
        if demand_col:
            try:
                origins_res = gpd.read_file(gpkg_path, layer=origins_layer)
                if demand_col in origins_res.columns:
                    d_stage = origins_res[demand_col].astype(float)
                    rec["demand_column"] = demand_col
                    rec["demand_sum"] = float(d_stage.sum())
                else:
                    logger.warning(
                        "Demand column '%s' not found in origins layer '%s' for stage '%s'.",
                        demand_col,
                        origins_layer,
                        stage_name,
                    )
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "Failed to read origins layer '%s' for stage '%s' demand stats: %s",
                    origins_layer,
                    stage_name,
                    exc,
                )

        records.append(rec)

    if not records:
        logger.warning("No valid stage records for occupancy stats, Excel will not be created.")
        return

    # Информация о сценарии для имени файла
    if scenario_type == "projected" and paid_parking_enabled:
        scenario_slug = f"projected_paid_{int(workers_release_rate * 100)}"
    elif scenario_type == "projected":
        scenario_slug = "projected"
    else:
        scenario_slug = "existing"

    df = pd.DataFrame(records)
    xlsx_path = output_dir / f"parking_stage_shares_{scenario_slug}.xlsx"
    logger.info("Saving stage occupancy stats to Excel: %s", xlsx_path)
    df.to_excel(xlsx_path, index=False, sheet_name="stage_shares")


def export_total_parks_usage(
    parks_input,
    park_id_col: str,
    base_cap_col: str,
    stage_outputs: dict[str, str],
    parks_layer: str,
    output_dir: "Path",
    scenario_type: str,
    paid_parking_enabled: bool,
    workers_release_rate: float,
) -> None:
    """
    Формирует финальный GeoPackage по парковкам, где для каждой парковки
    суммируется занятость по всем трём категориям пользователей.
    """
    import geopandas as gpd
    import pandas as pd
    from pathlib import Path

    if not stage_outputs:
        logger.warning("No stage outputs provided for total parks usage export.")
        return

    if parks_input is None or len(parks_input) == 0:
        logger.warning("Input parks GeoDataFrame is empty, cannot build total usage.")
        return

    # Базовая таблица: исходная емкость и геометрия
    base_cols = [park_id_col, base_cap_col, "geometry"]
    missing_base = [c for c in base_cols if c not in parks_input.columns]
    if missing_base:
        logger.warning(
            "Parks input is missing required columns %s, cannot build total usage.",
            missing_base,
        )
        return

    combined = parks_input[base_cols].copy()
    combined = combined.rename(columns={base_cap_col: "capacity_init_base"})
    combined = combined.set_index(park_id_col)

    stage_names: list[str] = []

    for stage_name, gpkg_path in stage_outputs.items():
        gpkg_path = Path(gpkg_path)
        if not gpkg_path.exists():
            logger.warning(
                "Stage results file not found for total usage (stage=%s): %s",
                stage_name,
                gpkg_path,
            )
            continue

        logger.info(
            "Adding stage '%s' parking usage from %s (layer=%s)",
            stage_name,
            gpkg_path,
            parks_layer,
        )

        parks_stage = gpd.read_file(gpkg_path, layer=parks_layer)
        if parks_stage.empty:
            logger.warning("No parks in results for stage '%s', skipping.", stage_name)
            continue

        required_cols = ["destination_id", "used", "capacity_init", "capacity_rem", "park_load"]
        missing_stage = [c for c in required_cols if c not in parks_stage.columns]
        if missing_stage:
            logger.warning(
                "Stage '%s' results missing required columns %s, skipping.",
                stage_name,
                missing_stage,
            )
            continue

        df_stage = parks_stage[required_cols].copy()
        df_stage = df_stage.rename(
            columns={
                "destination_id": park_id_col,
                "used": f"used_{stage_name}",
                "capacity_init": f"capacity_init_{stage_name}",
                "capacity_rem": f"capacity_rem_{stage_name}",
                "park_load": f"park_load_{stage_name}",
            }
        )
        df_stage = df_stage.set_index(park_id_col)

        combined = combined.join(df_stage, how="left")
        stage_names.append(stage_name)

    if not stage_names:
        logger.warning("No valid stage data to build total parks usage.")
        return

    # Заполняем пропуски нулями для числовых полей
    num_cols = [c for c in combined.columns if c != "geometry"]
    combined[num_cols] = combined[num_cols].fillna(0.0)

    # Общая занятость по всем категориям
    used_total = None
    for stage_name in stage_names:
        col = f"used_{stage_name}"
        if col in combined.columns:
            if used_total is None:
                used_total = combined[col].astype(float)
            else:
                used_total = used_total + combined[col].astype(float)

    if used_total is not None:
        combined["used_total"] = used_total
        cap_base = combined["capacity_init_base"].astype(float)
        with pd.option_context("mode.use_inf_as_na", True):
            combined["used_total_share_of_base"] = (
                used_total / cap_base.replace({0.0: pd.NA})
            )

    # Информация о сценарии для имени файла
    if scenario_type == "projected" and paid_parking_enabled:
        scenario_slug = f"projected_paid_{int(workers_release_rate * 100)}"
    elif scenario_type == "projected":
        scenario_slug = "projected"
    else:
        scenario_slug = "existing"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    gpkg_path = output_dir / f"parks_total_usage_{scenario_slug}.gpkg"
    logger.info("Saving total parks usage GeoPackage: %s", gpkg_path)

    combined.reset_index().to_file(
        gpkg_path,
        layer="parks_total_usage",
        driver="GPKG",
    )

    logger.info("Total parks usage GeoPackage successfully saved.")


def load_config(config_path: str = "config.json"):
    """
    Загружает конфигурацию из JSON файла.
    
    Parameters
    ----------
    config_path : str, default="config.json"
        Путь к файлу конфигурации
        
    Returns
    -------
    dict
        Словарь с конфигурацией
    """
    import json
    from pathlib import Path
    
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    return config


def create_probability_function(prob_config: dict):
    """
    Создает функцию вероятности на основе конфигурации.
    
    Parameters
    ----------
    prob_config : dict
        Конфигурация функции вероятности из JSON:
        {
            "type": "builtin" | "custom",
            "name": "p_walk_exponential" | "p_walk_piecewise" | путь к модулю,
            "parameters": {...}  # параметры для встроенных функций
        }
        
    Returns
    -------
    Callable
        Функция вероятности
    """
    from importlib import import_module
    
    prob_type = prob_config.get("type", "builtin")
    prob_name = prob_config.get("name", "p_walk_exponential")
    prob_params = prob_config.get("parameters", {})

    if prob_type == "builtin":
        # Встроенные функции
        if prob_name == "p_walk_exponential":

            def p_func(times):
                return p_walk_exponential(
                    times,
                    t0=prob_params.get("t0", 5.0),
                    t1=prob_params.get("t1", 10.0),
                    p_at_t1=prob_params.get("p_at_t1", 0.2),
                )

            return p_func
        elif prob_name == "p_walk_piecewise":

            def p_func(times):
                return p_walk_piecewise(
                    times,
                    t0=prob_params.get("t0", 5.0),
                    t1=prob_params.get("t1", 10.0),
                    p_at_t1=prob_params.get("p_at_t1", 0.2),
                )

            return p_func
        else:
            raise ValueError(f"Unknown builtin probability function: {prob_name}")

    elif prob_type == "custom":
        # Пользовательская функция из модуля
        if "." in prob_name:
            # Путь к модулю и функции: "my_module.my_function"
            module_path, func_name = prob_name.rsplit(".", 1)
            module = import_module(module_path)
            return getattr(module, func_name)
        else:
            raise ValueError(
                "For custom functions, provide full module path: 'my_module.my_function'"
            )

    else:
        raise ValueError(f"Unknown probability function type: {prob_type}")


if __name__ == "__main__":
    import json
    from pathlib import Path

    import geopandas as gpd
    import numpy as np

    # Basic logging setup for script run. Libraries can override this if needed.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    # Загружаем конфигурацию из JSON
    project_root = Path(__file__).parent
    config_path = project_root / "config.json"

    logger.info("Loading configuration from: %s", config_path)
    config = load_config(str(config_path))

    # Извлекаем пути
    paths = config["paths"]
    input_dir = project_root / paths["input_dir"]
    output_dir = project_root / paths["output_dir"]

    # Создаем директории если их нет
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    # Формируем пути к файлам
    roads_path = input_dir / paths["roads_file"]
    origins_path = input_dir / paths["origins_file"]
    parks_path = input_dir / paths["parks_file"]
    out_gpkg_path = output_dir / paths["output_file"]

    # Загружаем входные данные как GeoDataFrame
    logger.info(
        "Loading input data from files: roads=%s, origins=%s, parks=%s",
        roads_path,
        origins_path,
        parks_path,
    )
    roads = gpd.read_file(str(roads_path), layer=config["layers"]["roads_layer"])
    origins = gpd.read_file(str(origins_path), layer=config["layers"]["origins_layer"])
    parks = gpd.read_file(str(parks_path), layer=config["layers"]["parks_layer"])

    # --- Подготовка исходников: origins как кварталы с несколькими типами спроса ---
    # Ожидаемые поля:
    # - origin_id
    # - NASELENIE
    # - WORKERS
    # - RM (рабочие места)
    # - DITM, OrITM, DITI, OrITI  -> суммируются в POSETITELI
    visitor_components = ["DITM"] #, "OrITM", "DITI", "OrITI"
    missing_visitor_cols = [c for c in visitor_components if c not in origins.columns]
    if missing_visitor_cols:
        raise ValueError(
            f"Origins layer is missing visitor component columns: {missing_visitor_cols}"
        )

    logger.info("Computing POSETITELI as sum of %s", visitor_components)
    origins["POSETITELI"] = origins[visitor_components].sum(axis=1)

    # Категории спроса: население, рабочие, посетители
    default_categories = [
        {"name": "naselenie", "column": "NASELENIE"},
        {"name": "workers", "column": "WORKERS"},
        {"name": "posetiteli", "column": "POSETITELI"},
    ]
    demand_categories = config.get("demand_categories", default_categories)

    # Настройки сценария (существующее или проектное положение)
    scenario_config = config.get("scenario", {})
    scenario_type = scenario_config.get("type", "existing")  # "existing" или "projected"
    paid_parking_config = scenario_config.get("paid_parking", {})
    paid_parking_enabled = paid_parking_config.get("enabled", False)
    workers_release_rate = paid_parking_config.get("workers_release_rate", 0.9)
    
    if scenario_type == "projected" and paid_parking_enabled:
        logger.info(
            "Projected scenario enabled: paid parking will free %.0f%% of workers' occupied spaces",
            workers_release_rate * 100
        )

    # Создаем функцию вероятности из конфигурации
    prob_config = config["model_config"]["probability_function"]
    p_func = create_probability_function(prob_config)
    logger.info(
        "Using probability function: %s (type: %s)",
        prob_config["name"],
        prob_config["type"],
    )

    # Общие конфигурации графа и модели
    graph_cfg = GraphBuildConfig(
        walking_speed_kmh=config["graph_config"]["walking_speed_kmh"],
        time_field=config["graph_config"].get("time_field"),
        speed_field_kmh=config["graph_config"].get("speed_field_kmh"),
        bidirectional=config["graph_config"].get("bidirectional", True),
    )

    model_cfg = ModelConfig(
        cutoff_min=config["model_config"]["cutoff_min"],
        tol=config["model_config"]["tol"],
        max_iter=config["model_config"]["max_iter"],
        log_every=config["model_config"]["log_every"],
        verbose=config["model_config"]["verbose"],
        p_func=p_func,
    )

    # Настройки визуализации
    viz_enabled = config["visualization"].get("enabled", True)
    viz_root = output_dir / config["visualization"].get("output_dir", "visualizations")
    roads_path_for_viz = (
        str(roads_path) if config["visualization"].get("show_roads", True) else None
    )
    figsize = tuple(config["visualization"].get("figsize", [12, 10]))

    # Базовый путь для результатов
    base_gpkg = Path(out_gpkg_path)

    # Рабочий столбец емкости парковок для поэтапной загрузки
    park_id_col = config["columns"]["park_id_col"]
    base_cap_col = config["columns"]["park_capacity_col"]
    working_cap_col = f"{base_cap_col}_STAGE"
    parks[working_cap_col] = parks[base_cap_col].astype(float)

    # --- Запуск модели по трем категориям спроса ---
    last_cat_out_gpkg: Path | None = None
    last_eff_demand_col: str | None = None
    stage_outputs: dict[str, str] = {}
    stage_demands: dict[str, str] = {}

    for cat in demand_categories:
        cat_name = cat.get("name") or cat.get("column")
        demand_col = cat["column"]

        if demand_col not in origins.columns:
            raise ValueError(
                f"Demand column '{demand_col}' for category '{cat_name}' "
                f"not found in origins data."
            )

        # Специальное правило для населения: новый спрос D = NASELENIE * coeff1 * coeff2
        if demand_col == "NASELENIE":
            eff_demand_col = "D_NASELENIE"
            coeffs = cat.get("coefficients", {})
            mult1 = coeffs.get("first_multiplier", 0.5)
            mult2 = coeffs.get("second_multiplier", 0.3)
            logger.info(
                "Computing demand for '%s' as %s * %.2f * %.2f -> %s",
                cat_name,
                demand_col,
                mult1,
                mult2,
                eff_demand_col,
            )
            origins[eff_demand_col] = (
                (origins[demand_col].astype(float) * mult1) * mult2
            )
        # Специальное правило для рабочих:
        # 1) считаем коэффициент k = sum(WORKERS) / sum(RM)
        # 2) масштабируем RM: RM_scaled = RM * k
        # 3) спрос на парковки трудящихся D = RM_scaled * scaling_multiplier
        elif demand_col == "WORKERS":
            eff_demand_col = "D_WORKERS"
            if "RM" not in origins.columns:
                raise ValueError(
                    "Origins layer is missing 'RM' column required for workers demand."
                )

            total_workers = origins["WORKERS"].astype(float).sum()
            total_rm = origins["RM"].astype(float).sum()
            if total_rm <= 0:
                raise ValueError(
                    "Total RM is non-positive, cannot compute scaling coefficient for workers."
                )

            coeffs = cat.get("coefficients", {})
            scaling_mult = coeffs.get("scaling_multiplier", 0.35)
            share1_w = coeffs.get("share1", 0.763)
            share2_w = coeffs.get("share2", 0.92)
            k = (total_workers * share1_w * share2_w * scaling_mult) / total_rm
            logger.info(
                "Computing demand for '%s' using RM scaling: "
                "k = sum(WORKERS)*%.3f*%.3f*%.2f/sum(RM) = %.4f; "
                "%s = RM * k -> %s",
                cat_name,
                share1_w,
                share2_w,
                scaling_mult,
                k,
                demand_col,
                eff_demand_col,
            )
            origins[eff_demand_col] = origins["RM"].astype(float) * k
        # Специальное правило для посетителей:
        # 1) берем формулу коэффициента для рабочих:
        #    k_workers = ( total_workers * 0.763 * 0.92 * scaling_mult ) / total_rm
        # 2) заменяем множители на 0.3, 0.1, 0.7:
        #    k_vis_rm = ( total_workers * 0.3 * 0.1 * 0.7 ) / total_rm
        # 3) умножаем k_vis_rm на RM и получаем потенциальный спрос посетителей по RM
        # 4) суммируем этот потенциальный спрос по всем кварталам и делим на total_visitors
        # 5) получаем итоговый коэффициент k_vis и умножаем им посетителей по каждому кварталу
        elif demand_col == "POSETITELI":
            eff_demand_col = "D_POSETITELI"

            if "RM" not in origins.columns:
                raise ValueError(
                    "Origins data is missing 'RM' column required for visitors demand calculation."
                )
            if "WORKERS" not in origins.columns:
                raise ValueError(
                    "Origins data is missing 'WORKERS' column required for visitors demand calculation."
                )
            if "POSETITELI" not in origins.columns:
                raise ValueError(
                    "Origins data is missing 'POSETITELI' column required for visitors demand calculation."
                )

            total_workers = origins["WORKERS"].astype(float).sum()
            total_rm = origins["RM"].astype(float).sum()
            total_visitors = origins["POSETITELI"].astype(float).sum()

            if total_rm <= 0:
                raise ValueError(
                    "Total RM is non-positive, cannot compute scaling coefficient for visitors."
                )
            if total_visitors <= 0:
                raise ValueError(
                    "Total POSETITELI is non-positive, cannot compute scaling coefficient for visitors."
                )

            # Шаг 2: коэффициент по RM для потенциального спроса посетителей
            coeffs = cat.get("coefficients", {})
            share1 = coeffs.get("share1", 0.3)
            share2 = coeffs.get("share2", 0.1)
            share3 = coeffs.get("share3", 0.68)
            factor_workers_to_vis = share1 * share2 * share3
            k_vis = (total_workers * factor_workers_to_vis) / total_visitors

            logger.info(
                (
                    "Computing demand for '%s' using visitors scaling from workers: "
                    "sum(WORKERS)=%.3f; sum(RM)=%.3f; sum(POSETITELI)=%.3f; "
                    "factor_workers_to_vis=%.3f; k_vis_rm=%.6f; total_potential_vis_demand=%.3f; "
                    "k_vis=%.6f; %s = POSETITELI * k_vis -> %s"
                ),
                cat_name,
                total_workers,
                total_rm,
                total_visitors,
                factor_workers_to_vis,
                k_vis,
                demand_col,
                eff_demand_col,
            )

            origins[eff_demand_col] = origins["POSETITELI"].astype(float) * k_vis
        else:
            eff_demand_col = demand_col

        logger.info(
            "Running category '%s' with demand column '%s'", cat_name, eff_demand_col
        )

        # Путь к GeoPackage для этой категории
        cat_out_gpkg = base_gpkg.with_name(
            f"{base_gpkg.stem}_{cat_name}{base_gpkg.suffix}"
        )
        last_cat_out_gpkg = cat_out_gpkg
        last_eff_demand_col = eff_demand_col
        stage_outputs[cat_name] = str(cat_out_gpkg)
        stage_demands[cat_name] = eff_demand_col

        # Инициализируем проект
        project = ParkingProject(
        roads=roads,
        origins=origins,
        parks=parks,
            origin_id_col=config["columns"]["origin_id_col"],
            origin_demand_col=eff_demand_col,
        park_id_col=park_id_col,
            park_capacity_col=working_cap_col,
            graph_cfg=graph_cfg,
            model_cfg=model_cfg,
            out_gpkg_path=str(cat_out_gpkg),
        )

        # Запускаем расчеты
        project.run()

        # Сохраняем результаты
        project.save_results(
            origins_layer_name=config["layers"]["origins_result_layer"],
            parks_layer_name=config["layers"]["parks_result_layer"],
        )
        project.save_logs()

# После строки 860 (после project.save_logs()) добавить более детальную диагностику:

        # ДИАГНОСТИКА: проверяем емкость и спрос для восточных кварталов
        if cat_name == "posetiteli":
            logger.info("=== DETAILED DIAGNOSTICS: Visitors capacity and demand ===")
            park_out_diag = project.model.park_out_
            origins_out_diag = project.model.origin_out_
            
            # Загружаем результаты этапа рабочих для сравнения
            workers_gpkg = base_gpkg.with_name(f"{base_gpkg.stem}_workers{base_gpkg.suffix}")
            if workers_gpkg.exists():
                workers_origins = gpd.read_file(workers_gpkg, layer=config["layers"]["origins_result_layer"])
                workers_parks = gpd.read_file(workers_gpkg, layer=config["layers"]["parks_result_layer"])
                
                # Сравниваем coverage рабочих и посетителей
                merged = origins_out_diag.merge(
                    workers_origins[[config["columns"]["origin_id_col"], "coverage"]],
                    on=config["columns"]["origin_id_col"],
                    suffixes=("_visitors", "_workers")
                )
                
                # Кварталы, где у рабочих coverage = 0, а у посетителей coverage = 1
                problem_quarters = merged[
                    (merged["coverage_workers"] == 0) & (merged["coverage_visitors"] >= 0.9)
                ]
                
                logger.info("Quarters with workers coverage=0 but visitors coverage>=0.9: %d", len(problem_quarters))
                
                if len(problem_quarters) > 0:
                    logger.info("Problem quarters details:")
                    logger.info("  - Mean visitors demand: %.6f", problem_quarters["demand"].mean())
                    logger.info("  - Mean visitors served: %.6f", problem_quarters["served"].mean())
                    logger.info("  - Mean visitors remaining_effective: %.6f", 
                               problem_quarters["remaining_effective"].mean())
                    
                    # Проверяем, какие парковки используются посетителями в этих кварталах
                    pair_out_diag = project.model.pair_out_
                    problem_origin_ids = problem_quarters[config["columns"]["origin_id_col"]].values
                    problem_pairs = pair_out_diag[
                        pair_out_diag[config["columns"]["origin_id_col"]].isin(problem_origin_ids)
                    ]
                    
                    if len(problem_pairs) > 0:
                        # Проверяем емкость парковок, используемых посетителями
                        used_park_ids = problem_pairs["destination_id"].unique()
                        used_parks = park_out_diag[park_out_diag["destination_id"].isin(used_park_ids)]
                        logger.info("  - Parks used by visitors in problem quarters: %d", len(used_parks))
                        logger.info("  - Mean capacity_init: %.2f", used_parks["capacity_init"].mean())
                        logger.info("  - Mean capacity_rem: %.2f", used_parks["capacity_rem"].mean())
                        logger.info("  - Parks with capacity_rem=0: %d", (used_parks["capacity_rem"] == 0).sum())
                        
                        # Проверяем, какие парковки были доступны после рабочих
                        if "destination_id" in workers_parks.columns:
                            workers_parks_idxed = workers_parks.set_index("destination_id")
                            used_parks_workers = workers_parks_idxed.loc[
                                workers_parks_idxed.index.intersection(used_park_ids)
                            ]
                            logger.info("  - Mean capacity_rem after workers: %.2f", 
                                       used_parks_workers["capacity_rem"].mean())
                            logger.info("  - Parks with capacity_rem=0 after workers: %d", 
                                       (used_parks_workers["capacity_rem"] == 0).sum())
            
            logger.info("=== END DETAILED DIAGNOSTICS ===")

        # Обновляем доступную емкость парковок для следующей категории
        park_out = project.model.park_out_
        # В выходной таблице парков ID колонка называется "destination_id"
        park_out_idxed = park_out.set_index("destination_id")[["capacity_init", "used", "capacity_rem"]].astype(float)

        if cat_name == "naselenie":
            # После загрузки парковок по населению освобождаем 94% занятых мест.
            # used_new = used * (1 - 0.94) = 0.06 * used
            # новая доступная емкость = capacity_init - used_new
            logger.info(
                "Freeing 94%% of occupied spaces after '%s' stage to use as new capacity",
                cat_name,
            )
            cap_init = park_out_idxed["capacity_init"]
            used = park_out_idxed["used"]
            new_cap_by_id = (cap_init - 0.06 * used).clip(lower=0.0)
        elif cat_name == "workers" and scenario_type == "projected" and paid_parking_enabled:
            # Проектное решение: введение платных парковок
            # Освобождаем workers_release_rate% занятых трудящимися мест
            # used_new = used * (1 - workers_release_rate)
            # новая доступная емкость = capacity_init - used_new
            logger.info(
                "Projected scenario: freeing %.0f%% of workers' occupied spaces due to paid parking",
                workers_release_rate * 100,
            )
            cap_init = park_out_idxed["capacity_init"]
            used = park_out_idxed["used"]
            new_cap_by_id = (cap_init - (1.0 - workers_release_rate) * used).clip(lower=0.0)
        else:
            # Для последующих категорий используем расчётную оставшуюся емкость
            # Обрезаем отрицательные значения до 0 (защита от численных ошибок)
            new_cap_by_id = park_out_idxed["capacity_rem"].clip(lower=0.0)

        parks[working_cap_col] = parks[park_id_col].map(new_cap_by_id).fillna(0.0)

        # Визуализации для этой категории
        if viz_enabled:
            logger.info("Creating visualizations for category '%s'...", cat_name)
            viz_output_dir = viz_root / cat_name
            
            # Формируем информацию о сценарии для визуализации
            # Проектное решение с платными парковками показываем только для posetiteli
            # (после того, как освобождение уже применено)
            scenario_label = None
            if cat_name == "posetiteli" and scenario_type == "projected" and paid_parking_enabled:
                scenario_label = f"Проектное решение: платные парковки (освобождение {int(workers_release_rate * 100)}%)"
            elif cat_name == "posetiteli" and scenario_type == "projected":
                scenario_label = "Проектное решение"
            elif scenario_type == "projected" and paid_parking_enabled:
                # Для naselenie и workers показываем, что это проектный сценарий, но платные парковки еще не применены
                scenario_label = "Проектное решение (до введения платных парковок)"
            elif scenario_type == "projected":
                scenario_label = "Проектное решение"
            else:
                scenario_label = "Существующее положение"
            
            project.visualize(
                output_dir=str(viz_output_dir),
                roads_path=roads_path_for_viz,
                figsize=figsize,
                scenario_info=scenario_label,
            )

    logger.info("All done! Results saved to: %s", output_dir)

    # --- Статистика по парковкам внутри center_bound ---
    paths_cfg = config.get("paths", {})
    layers_cfg = config.get("layers", {})
    center_file = paths_cfg.get("center_bound_file")
    center_layer = layers_cfg.get("center_bound_layer", "center_bound")

    # Статистика по центру для финальной категории (посетители)
    if center_file and last_cat_out_gpkg is not None:
        center_path = input_dir / center_file
        center_output_dir = output_dir / "center_stats"
        compute_center_bound_stats(
            results_gpkg_path=str(last_cat_out_gpkg),
            parks_layer=layers_cfg.get("parks_result_layer", "parks_result"),
            origins_layer=layers_cfg.get("origins_result_layer", "origins_result"),
            demand_column=last_eff_demand_col,
            center_bound_path=str(center_path),
            center_bound_layer=center_layer,
            output_dir=center_output_dir,
            scenario_type=scenario_type,
            paid_parking_enabled=paid_parking_enabled,
            workers_release_rate=float(workers_release_rate),
        )

    # Сводка по доле занятости парковок по этапам
    if stage_outputs:
        stage_stats_dir = output_dir / "stage_stats"
        export_stage_occupancy_stats(
            stage_outputs=stage_outputs,
            stage_demands=stage_demands,
            parks_layer=layers_cfg.get("parks_result_layer", "parks_result"),
            origins_layer=layers_cfg.get("origins_result_layer", "origins_result"),
            output_dir=stage_stats_dir,
            scenario_type=scenario_type,
            paid_parking_enabled=paid_parking_enabled,
            workers_release_rate=float(workers_release_rate),
        )

        # Финальный GeoPackage с суммарной занятостью по всем категориям пользователей
        export_total_parks_usage(
            parks_input=parks,
            park_id_col=park_id_col,
            base_cap_col=base_cap_col,
            stage_outputs=stage_outputs,
            parks_layer=layers_cfg.get("parks_result_layer", "parks_result"),
            output_dir=output_dir,
            scenario_type=scenario_type,
            paid_parking_enabled=paid_parking_enabled,
            workers_release_rate=float(workers_release_rate),
        )

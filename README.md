# 智慧导航 (Smart Navigation) — 多场景智能路径导航系统

**数据结构与算法课程项目 · Web 版 + 桌面版双平台**

融合校园室内导航与城市多场景智能路径规划，手写全部核心数据结构和算法，支持 Web 可视化与 tkinter 桌面双端交互。

---

## 🖥 Web 版 — CampusPath 校园室内导航

模拟一栋 4 层教学楼（~74 个节点，~140 条边），实现 7 种路径搜索算法变体，通过 Flask + Canvas 提供交互式 Web 演示。

### 核心特性

- **手写数据结构**：邻接表图、MinHeap(含 decrease_key)、Queue、Stack、HashMap
- **手写算法**：Dijkstra、A\*(3 种启发式)、BFS、双向 BFS、双向 Dijkstra
- **创新点**：楼层感知启发式(Floor-Aware)、多层楼跨层导航、双向加权搜索
- **实验对比**：10 个测试场景 × 7 个算法变体，4 项量化指标
- **69 个 pytest 测试**，全部通过

### 快速启动

```bash
pip install -r requirements.txt
python -m pytest backend/tests/ -v    # 69 tests
python backend/app.py                 # http://localhost:5001
```

### 前端页面 (8 页 SPA)

| 页面 | 功能 |
|------|------|
| 导航仪表盘 | 建筑统计、最近搜索、快速导航 |
| 路径导航 | Canvas 地图、搜索框、5 算法寻路、动画播放、多楼层 |
| 房间目录 | 搜索过滤、房间详情弹窗、房间元数据 |
| 算法基准 | 批量对比 (10 场景)、Chart.js 图表、汇总统计 |
| 无障碍通道 | 轮椅模式、电梯等待时间模拟、绿色路径 |
| 系统诊断 | 图验证、度分布直方图、孤立节点检测 |
| 智慧导航 | 4 地图场景、8 算法、POI 搜索、实时交通、车辆监管、SSE 流 |
| 关于系统 | 技术栈、项目信息 |

### Web API 端点 (56 total)

**Campus Core (22 endpoints):**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/building` | 建筑元数据 |
| GET | `/api/building/floor/<n>` | 楼层布局 |
| GET | `/api/building/all-nodes` | 全部节点 |
| GET | `/api/building/stats` | 图统计 |
| GET | `/api/building/validate` | 图验证 |
| GET | `/api/building/degree-distribution` | 度分布 |
| GET | `/api/building/isolated-nodes` | 孤立节点 |
| POST | `/api/path` | 单次寻路 |
| POST | `/api/compare` | 全部算法对比 |
| POST | `/api/batch-compare` | 批量对比 |
| POST | `/api/batch-benchmark` | 批量基准 (含 Chart.js 数据) |
| GET | `/api/algorithm-steps/<algo>` | 动画步骤 |
| POST | `/api/directions` | 转向指引 |
| POST | `/api/accessible-path` | 无障碍路径 (含电梯等待) |
| GET | `/api/rooms/search` | 房间搜索 |
| GET | `/api/room/<id>` | 房间详情 |
| GET/POST | `/api/recent` | 最近搜索历史 |
| GET | `/api/meta/algorithms` | 算法元数据 |

**SmartNav (34 endpoints + SSE):**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/smart/scenes` | 列出所有场景 |
| GET | `/api/smart/scenes/<id>` | 场景详情 |
| POST | `/api/smart/scenes/<id>/activate` | 激活场景 |
| GET | `/api/smart/scenes/<id>/stats` | 场景统计 |
| POST | `/api/smart/path` | 路径规划 (多模式) |
| POST | `/api/smart/compare` | 全算法对比 |
| POST | `/api/smart/path/waypoints` | 途经点路径 |
| POST | `/api/smart/path/accessible` | 无障碍路径 |
| GET | `/api/smart/search/nearby` | 附近 POI 搜索 |
| GET | `/api/smart/search/categories` | POI 分类 |
| GET | `/api/smart/traffic` | 交通状态查询 |
| POST | `/api/smart/traffic/congestion` | 设置拥堵 |
| POST | `/api/smart/traffic/blockage` | 设置阻断 |
| DELETE | `/api/smart/traffic` | 重置交通 |
| GET/POST | `/api/smart/vehicles` | 车辆列表/添加 |
| DELETE | `/api/smart/vehicles/<id>` | 删除车辆 |
| PUT | `/api/smart/vehicles/<id>/speed` | 调整速度 |
| PUT | `/api/smart/vehicles/<id>/control` | 车辆控制 |
| POST | `/api/smart/navigation/start` | 开始导航 |
| POST | `/api/smart/navigation/update` | 更新导航位置 |
| POST | `/api/smart/navigation/reroute` | 重路由 |
| POST | `/api/smart/navigation/stop` | 停止导航 |
| GET | `/api/smart/navigation/status` | 导航状态 |
| GET | `/api/smart/navigation/stream` | SSE 实时流 |
| POST | `/api/smart/simulation/traffic/start` | 交通模拟 |
| POST | `/api/smart/simulation/traffic/stop` | 停止交通模拟 |
| POST | `/api/smart/simulation/vehicle/start` | 车辆模拟 |
| POST | `/api/smart/simulation/vehicle/stop` | 停止车辆模拟 |
| GET | `/api/smart/simulation/status` | 模拟状态 |
| GET | `/api/smart/meta` | SmartNav 元数据 |
| GET/DELETE | `/api/smart/history` | 搜索历史 |
| GET | `/api/smart/nodes/<scene>/<node>` | 节点详情 |

---

## 🖱 桌面版 — SmartNavigation 多场景智慧导航

wxPython 桌面应用，支持 4 种地图场景 × 8 种路径规划算法，6 大功能标签页。

### 核心特性

- **🗺 4 种地图场景**：校园(Campus)、商场(Mall)、城區(City District)、地下(Underground)
- **🔍 8 种路径算法**：Dijkstra、A\*、BFS、双向 Dijkstra、双向 BFS、拥堵避让、多目标优化、动态重路由
- **🧭 6 大功能标签页**：路径规划、附近搜索、实时导航、算法对比、车辆监控、地图管理
- **🚦 实时交通模拟**：拥堵因子、路段阻断/恢复、流量模拟
- **🚗 车辆监控**：多车辆追踪、运输模式过滤(步行/自行车/汽车/公交/地铁)
- **36 个 pytest 测试**，全部通过

### 快速启动

```bash
pip install -r requirements.txt
python -m pytest desktop/tests/ -v    # 36 tests
python desktop/run.py                 # 启动桌面 GUI
```

---

## 📁 项目结构

```
智慧导航/
├── backend/                       # Web 后端 (Flask API)
│   ├── app.py                     # Flask 应用 (22 端点, 端口 5001)
│   ├── routes_smart.py            # SmartNav API (34 端点 + SSE)
│   ├── algorithms/                # 路径算法 (13 文件含扩展)
│   │   ├── dijkstra.py            # Dijkstra
│   │   ├── a_star.py              # A* (3 启发式)
│   │   ├── bfs.py                 # BFS
│   │   ├── bidirectional.py       # 双向搜索 (BFS + Dijkstra)
│   │   ├── congestion_avoidance.py    # 拥堵避让
│   │   ├── multi_criteria.py      # 多目标优化
│   │   ├── reroute.py             # 动态重路由
│   │   ├── extended_dijkstra.py   # 扩展 Dijkstra
│   │   ├── extended_a_star.py     # 扩展 A*
│   │   ├── extended_bfs.py        # 扩展 BFS
│   │   ├── extended_bidirectional.py  # 扩展双向
│   │   ├── min_heap.py            # MinHeap
│   │   └── queue_stack.py         # Queue + Stack
│   ├── core/                      # 核心数据结构
│   ├── models/                    # 数据模型 (Graph, Node, Building, Traffic, Vehicle...)
│   ├── services/                  # 业务服务 (路径, 搜索, 交通, 车辆, 导航)
│   ├── simulation/                # 模拟器 (交通+车辆)
│   ├── data/                      # 校园地图 + 测试场景
│   └── tests/                     # 后端测试 (69 cases)
├── frontend/                      # Web 前端
│   └── index.html                 # SPA (8 页面 + Canvas + SSE)
├── desktop/                       # 🆕 桌面应用 (wxPython)
│   ├── run.py                     # 桌面版入口
│   ├── smart_navigation/          # 桌面版核心包
│   │   ├── algorithms/            # 8 种路径算法
│   │   │   ├── dijkstra.py        # Dijkstra 最短路径
│   │   │   ├── a_star.py          # A* 启发式搜索
│   │   │   ├── bfs.py             # BFS 广度优先
│   │   │   ├── bidirectional.py   # 双向搜索
│   │   │   ├── congestion_avoidance.py  # 拥堵避让
│   │   │   ├── multi_criteria.py  # 多目标优化
│   │   │   └── reroute.py         # 动态重路由
│   │   ├── core/                  # 核心数据结构
│   │   │   ├── graph.py           # NavGraph (邻接表)
│   │   │   ├── node.py            # NavNode + NavNodeType
│   │   │   ├── edge.py            # Edge (含 RoadType)
│   │   │   ├── min_heap.py        # MinHeap
│   │   │   ├── queue_stack.py     # Queue + Stack
│   │   │   └── map_manager.py     # 地图加载管理
│   │   ├── models/                # 领域模型
│   │   │   ├── map_scene.py       # 场景定义
│   │   │   ├── path_result.py     # 路径结果
│   │   │   ├── traffic.py         # 交通模型
│   │   │   ├── transport.py       # 运输模式
│   │   │   └── vehicle.py         # 车辆模型
│   │   ├── services/              # 业务服务层
│   │   │   ├── path_service.py    # 路径规划服务
│   │   │   ├── search_service.py  # 附近搜索服务
│   │   │   ├── traffic_service.py # 交通管理服务
│   │   │   ├── vehicle_service.py # 车辆监控服务
│   │   │   └── navigation_service.py  # 实时导航服务
│   │   ├── gui_wx/                   # GUI 界面 wxPython (6 标签页)
│   │   │   ├── app_window.py      # 主窗口
│   │   │   ├── path_planning_tab.py    # 路径规划
│   │   │   ├── nearby_search_tab.py    # 附近搜索
│   │   │   ├── realtime_nav_tab.py     # 实时导航
│   │   │   ├── comparison_panel.py     # 算法对比
│   │   │   ├── vehicle_monitor_tab.py  # 车辆监控
│   │   │   ├── map_management_tab.py   # 地图管理
│   │   │   ├── map_canvas.py      # 地图画布
│   │   │   ├── styles.py          # UI 样式
│   │   │   └── theme.py           # 暗色主题
│   │   ├── simulation/            # 模拟器
│   │   │   ├── traffic_simulator.py    # 交通模拟
│   │   │   └── vehicle_simulator.py    # 车辆模拟
│   │   └── data/maps/             # 4 张地图 JSON
│   │       ├── campus_map.json
│   │       ├── mall_map.json
│   │       ├── city_district.json
│   │       └── underground.json
│   └── tests/                     # 桌面测试 (36 cases)
├── report/main.tex                # LaTeX 课程报告
├── requirements.txt
└── README.md
```

## 算法对比

### Web 版（10 场景聚合）

| 算法 | 路径最优 | 探索效率 |
|------|---------|---------|
| BFS | ✗ (忽略权重) | ★★★★★ |
| Dijkstra | ✓ 最优 | ★★★ |
| A\* (Euclidean) | ✓ 最优 | ★★★★ |
| A\* (Floor-Aware) | ✓ 最优 | ★★★★★ |
| Bidirectional BFS | ✗ | ★★★★ |
| Bidirectional Dijkstra | ✓ 最优 | ★★★★ |

### 桌面版（8 算法）

| 算法 | 支持模式过滤 | 拥堵感知 | 多目标 | 动态重规划 |
|------|:---:|:---:|:---:|:---:|
| Dijkstra | ✓ | ✗ | ✗ | ✗ |
| A\* | ✓ | ✗ | ✗ | ✗ |
| BFS | ✓ | ✗ | ✗ | ✗ |
| Bidirectional Dijkstra | ✓ | ✗ | ✗ | ✗ |
| Bidirectional BFS | ✓ | ✗ | ✗ | ✗ |
| 拥堵避让 | ✓ | ✓ | ✗ | ✗ |
| 多目标优化 | ✓ | ✗ | ✓ | ✗ |
| 动态重路由 | ✓ | ✓ | ✗ | ✓ |

## 测试覆盖

```bash
# Web 版 (69 tests)
python -m pytest backend/tests/ -v

# 桌面版 (36 tests)
python -m pytest desktop/tests/ -v

# 全部 (105 tests)
python -m pytest backend/tests/ desktop/tests/ -v
```

## 技术栈

Python 3.x · Flask · HTML5 Canvas · wxPython · pytest · LaTeX · Chart.js

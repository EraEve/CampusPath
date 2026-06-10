# CampusPath — 校园室内导航系统

**数据结构与算法 课程代码报告**

基于多算法的校园室内路径导航系统，手写全部核心数据结构和算法，Web 可视化演示。

## 项目概述

模拟一栋 4 层教学楼（~74 个节点，~140 条边），实现 5 种路径搜索算法，通过 Flask + Canvas 提供交互式 Web 演示。

## 核心特性

- **手写数据结构**：邻接表图、MinHeap(含 decrease_key)、Queue、Stack、HashMap
- **手写算法**：Dijkstra、A\*(3 种启发式)、BFS、双向 BFS、双向 Dijkstra
- **创新点**：楼层感知启发式(Floor-Aware)、多层楼跨层导航、双向加权搜索
- **实验对比**：10 个测试场景 × 7 个算法变体，4 项量化指标
- **69 个 pytest 测试**，全部通过

## 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行测试
python -m pytest backend/tests/ -v

# 3. 启动 Flask 服务
python backend/app.py

# 4. 打开浏览器
# http://localhost:5001
```

## 项目结构

```
CampusPath/
├── backend/
│   ├── app.py                 # Flask API (8 端点)
│   ├── models/                # 数据模型
│   │   ├── node.py            # Node + NodeType
│   │   ├── graph.py           # AdjacencyListGraph
│   │   └── building.py        # Building 模型
│   ├── algorithms/            # 核心算法
│   │   ├── min_heap.py        # MinHeap (decrease_key)
│   │   ├── queue_stack.py     # Queue + Stack
│   │   ├── dijkstra.py        # Dijkstra ★
│   │   ├── a_star.py          # A* (3 启发式) ★
│   │   ├── bfs.py             # BFS
│   │   └── bidirectional.py   # 双向搜索
│   ├── data/                  # 地图数据
│   │   ├── campus_building.json
│   │   └── test_scenarios.json
│   └── tests/                 # 测试 (69 cases)
├── frontend/                  # Web 前端
│   ├── index.html             # SPA
│   ├── css/style.css
│   └── js/ (api.js, map_renderer.js, animation.js)
├── report/main.tex            # LaTeX 课程报告
├── requirements.txt
└── README.md
```

## API 端点

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/building` | 建筑元数据 |
| GET | `/api/building/floor/<n>` | 楼层布局 |
| GET | `/api/building/all-nodes` | 全部节点 |
| POST | `/api/path` | 单次寻路 |
| POST | `/api/compare` | 全部算法对比 |
| POST | `/api/batch-compare` | 批量对比 |
| GET | `/api/algorithm-steps/<algo>` | 动画步骤 |

## 算法对比（10 场景聚合）

| 算法 | 路径最优 | 探索效率 |
|------|---------|---------|
| BFS | ✗ (忽略权重) | ★★★★★ |
| Dijkstra | ✓ 最优 | ★★★ |
| A\* (Euclidean) | ✓ 最优 | ★★★★ |
| A\* (Floor-Aware) | ✓ 最优 | ★★★★★ |
| Bidirectional BFS | ✗ | ★★★★ |
| Bidirectional Dijkstra | ✓ 最优 | ★★★★ |

## 技术栈

Python 3.x · Flask · HTML5 Canvas · JavaScript · pytest · LaTeX

import matplotlib.pyplot as plt
import numpy as np

# 1. 데이터 준비 (Data Preparation)
# 이전 데이터: 움직임 경로
path_coords = np.array([
    [0.155172, 1.02788, 0.077519], [0.080303, 1.025814, 0.099518],
    [0.062311, 1.027976, 0.024914], [0.118603, 1.030051, 0.001394],
    [0.118332, 1.030258, 0.001557], [0.118381, 1.030119, 0.001488],
    [0.049962, 1.027467, 0.052289], [0.088821, 1.026794, 0.100471],
    [0.088219, 1.027051, 0.100683], [0.087651, 1.027537, 0.100673],
    [0.032653, 1.026744, 0.099995], [0.064658, 1.026578, 0.067131],
    [0.061727, 1.026291, 0.014478], [0.069552, 1.026832, -0.0306],
    [0.147231, 1.031043, -0.054], [0.150035, 1.029003, -0.0528],
    [0.160894, 1.028244, -0.0906], [0.163931, 1.02982, -0.09051],
    [0.164725, 1.029339, -0.09701], [0.164701, 1.029356, -0.09699],
    [0.102557, 1.029842, -0.08151], [0.084376, 1.028094, -0.09321],
    [0.084341, 1.028047, -0.09322], [0.086878, 1.02975, -0.04226],
    [0.086957, 1.026724, -0.03314], [0.087026, 1.026518, -0.03313],
    [0.087157, 1.026395, -0.03312], [0.030427, 1.024666, 0.015397],
    [0.030275, 1.02458, 0.014908], [-0.03274, 1.023918, 0.048171],
    [-0.05644, 1.025002, -0.0106], [-0.05637, 1.024986, -0.0106],
    [-0.11466, 1.025156, 0.062247], [-0.15865, 1.025343, 0.093005],
    [-0.15906, 1.026259, 0.09314], [-0.15932, 1.026337, 0.093071],
    [-0.15515, 1.025996, 0.0271], [-0.15498, 1.025775, 0.027117],
    [-0.08998, 1.025395, 0.019033], [-0.09001, 1.025386, 0.019115],
    [-0.05472, 1.027023, -0.00217], [-0.05492, 1.027389, -0.00217],
    [-0.0549, 1.02703, -0.00241], [-0.05509, 1.027189, -0.00237],
    [-0.08932, 1.028621, -0.07596], [-0.10107, 1.009445, -0.0455],
    [-0.10104, 1.009851, -0.04581], [-0.15407, 1.010877, -0.07468],
    [-0.15353, 1.009675, -0.07487], [-0.10091, 1.009755, -0.07684],
    [-0.10105, 1.010087, -0.07684], [-0.10112, 1.010232, -0.07684]
])

# 새로 제공된 데이터: 움직일 수 있는 영역의 네 꼭짓점
area_coords = np.array([
    [0.183817744, 1.012222171, 0.146083131],
    [0.15868628, 1.011237502, -0.106446728],
    [-0.185148239, 1.010279179, -0.087205842],
    [-0.190332651, 1.012231112, 0.166426137]
])


# 2. 정사영을 위한 기준 평면 설정
# 평면의 원점을 첫 번째 점으로 설정
plane_origin = area_coords[0]
# 평면 위의 두 벡터를 계산 (두 점을 연결)
# 네 번째 점과 첫 번째 점을 연결하여 평면의 새로운 u축(x축)으로 사용
vec1 = area_coords[3] - plane_origin
# 두 번째 점과 첫 번째 점을 연결
vec2 = area_coords[1] - plane_origin

# 평면의 법선 벡터 계산 (외적). 이 벡터가 우리가 바라보는 시선 방향이 됨.
normal_vector = np.cross(vec1, vec2)
normal_vector = normal_vector / np.linalg.norm(normal_vector) # 단위 벡터로 정규화

# 평면의 새로운 좌표축(기저 벡터) 계산
u_axis = vec1 / np.linalg.norm(vec1) # u축 (새로운 x축)
v_axis = np.cross(normal_vector, u_axis) # v축 (새로운 y축)


# 3. 3D 좌표를 2D로 정사영하는 함수
def project_to_plane(points_3d, origin, u, v):
    # 원점 기준으로 벡터 계산
    vectors = points_3d - origin
    # 내적(dot product)을 이용해 새로운 u, v 좌표 계산
    coords_2d_u = np.dot(vectors, u)
    coords_2d_v = np.dot(vectors, v)
    return np.vstack((coords_2d_u, coords_2d_v)).T

# 경로와 영역 좌표를 2D로 변환
projected_path = project_to_plane(path_coords, plane_origin, u_axis, v_axis)
projected_area = project_to_plane(area_coords, plane_origin, u_axis, v_axis)


# 4. 2D 시각화
fig, ax = plt.subplots(figsize=(10, 8))

# 영역 그리기 (반투명한 다각형으로 채우기)
# projected_area 좌표를 닫힌 도형으로 만들기 위해 첫 좌표를 마지막에 추가
area_polygon = np.vstack([projected_area, projected_area[0]])
ax.fill(area_polygon[:, 0], area_polygon[:, 1], 'skyblue', alpha=0.5, label='Movable Area')
ax.plot(area_polygon[:, 0], area_polygon[:, 1], 'k--', label='Area Boundary') # 영역 경계선

# 경로 그리기
ax.plot(projected_path[:, 0], projected_path[:, 1], 'r-o', markersize=4, label='Movement Path')

# 시작점과 끝점 강조
ax.plot(projected_path[0, 0], projected_path[0, 1], 'go', markersize=10, label='Start')
ax.plot(projected_path[-1, 0], projected_path[-1, 1], 'bo', markersize=10, label='End')

# 그래프 설정
ax.set_title('2D Orthographic Projection of 3D Path', fontsize=16)
ax.set_xlabel("Projected U-axis (새로운 X축)")
ax.set_ylabel("Projected V-axis (새로운 Y축)")
ax.set_aspect('equal', 'box') # 가로, 세로 비율을 동일하게 맞춰 왜곡 방지
ax.grid(True)
ax.legend()

plt.show()
# **Mag to the Future: 자성 패치 상태 예측 모듈**

## 개요 (Overview)

본 저장소는 'Mag to the Future' 연구의 핵심 구성요소인 **자성 패치 상태 예측 모듈(Magnetic Patch State Prediction Module)** 의 소스 코드와 방법론을 담고 있습니다.

이 모듈의 역할은 **2D 홀센서 어레이(Hall Sensor Array)** 로부터 수집된 원본 자기장 데이터를 입력받아, 특정 영역 위에 놓인 **자성 패치의 상태 [위치(position) ~및 회전(rotation)~]를 정확하게 추정** 하는 것입니다. 여기서 산출된 상태 정보는 연구의 최종 목표를 달성하기 위한 필수적인 중간 데이터로 활용됩니다.

<br>

## 모듈의 주요 기능 (Key Features)

  * **다차원 센서 입력 처리**: 6x4x3 (총 72개)의 복합적인 자기장 벡터 값을 입력으로 처리
  * **6-DOF 상태 정보 추정**: 3차원 위치(x, y, z)~와 3차원 회전(quaternion) 정보를 동시에~ 산출
  * **MLP 기반 상태 예측**: MLP(다층 퍼셉트론) 모델을 통해 센서 값과 패치 상태 간의 복잡한 비선형 관계를 학습
  * **좌표계 정규화**: 물리적 센서의 코너 위치를 기준으로 좌표계를 변환하여 모델 학습의 일관성 및 정확도 확보

<br>

-----

## 개발 방법론 (Methodology)

### 1\. 입력 데이터 (Input Data)

  * **센서 구성**: **6x4** 격자 형태로 배열된 **24개** 의 3축 홀센서.
  * **데이터 형태**: 각 센서에서 측정된 자기장 벡터 값 **(Bx, By, Bz)** .
  * **입력 벡터**: 모델의 입력은 **72개(24센서 x 3축)** 의 센서 값으로 구성된 1차원 벡터입니다.
      * Input Vector Shape: `(batch_size, 72)`

### 2\. 모델 구조 (Model Architecture)

센서 값과 패치 상태 간의 비선형 관계를 효과적으로 학습하기 위해 **MLP(다층 퍼셉트론)** 를 기반으로 모델을 구성하였습니다.

1.  **입력층 (Input Layer)**: 72개의 센서 값을 입력받습니다.
2.  **은닉층 (Hidden Layers)**: 다수의 `Linear` 레이어와 `ReLU` 활성화 함수, `Dropout`을 통해 입력 데이터의 핵심 특징을 학습합니다.
3.  **출력층 (Output Layer)**: 최종적으로 **위치(x, y, z)** 를 나타내는 3개의 값을 출력합니다.

<br>

-----

## 파일 구조 (Project Structure)

```
mag-to-the-future/
├── data/
│   ├── device_geometry.csv       # 코너 위치 등 장치 기구 정보
│   └── training_data.csv         # 원본 센서 및 트래커 데이터
├── models/
│   └── hall_sensor_model.pth     # 학습된 모델 가중치
├── processing.py                 # 1. 데이터 전처리 및 좌표계 변환 스크립트
├── models.py                     # 2. MLP 모델 아키텍처 정의
├── train.py                      # 3. 모델 학습 스크립트
├── requirements.txt              # 필요한 Python 패키지 목록
└── README.md                     # 프로젝트 설명서
```

<br>

-----

## 시작하기 (Getting Started)

### 설치 (Installation)

1.  저장소를 클론합니다.
    ```sh
    git clone https://github.com/KevinTheRainmaker/MagToTheFuture.git
    cd MagToTheFuture
    ```
2.  필요한 패키지를 설치합니다.
    ```sh
    python -m pip install -r requirements.txt
    ```
3.  모델, 스케일러 파일을 다운로드 합니다.
    https://drive.google.com/drive/folders/12n0XMZAh_2DVf7lELc3a9fEx2NTGd5Ds?usp=sharing
    
### 사용법 (Usage)

**1단계: 데이터 전처리**

`training_data_wide.csv`의 트래커 좌표를 `device_geometry.csv` 기준으로 변환하고, 센서 데이터를 정규화하여 학습용 파일을 생성합니다.

```sh
python process_data.py
```

  * **출력**: `processed_training_data_advanced.csv` 파일이 생성됩니다.

**2단계: 모델 학습**

전처리된 데이터를 사용하여 MLP 모델을 학습시킵니다. 학습이 완료되면 최적의 모델 가중치(`hall_sensor_model.pth`)와 손실 그래프(`loss_graph.png`)가 저장됩니다.

```sh
python train.py
```

<br>

-----

## 라이선스 (License)

본 프로젝트는 [MIT License](https://opensource.org/licenses/MIT)를 따릅니다.

<br>

*CO-AUTHORED: Mag to the Future*

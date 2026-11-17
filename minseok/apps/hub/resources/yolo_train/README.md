# yolo_train — 얼굴 탐지 파인튜닝 데이터셋

`LocalYoloDatasetAdapter`(adapter/outbound)가 이 디렉토리의 `data.yaml`을
훈련 유스케이스(`FaceTrainingInteractor`)에 공급한다.

## 구조 (ultralytics YOLO 표준 포맷)

```
yolo_train/
├── data.yaml          # 데이터셋 설정 (클래스: 0 = face)
├── images/
│   ├── train/         # 훈련 이미지 (.jpg / .png)
│   └── val/           # 검증 이미지
└── labels/
    ├── train/         # 이미지와 같은 파일명의 .txt 라벨
    └── val/
```

## 라벨 포맷

이미지 1장당 같은 이름의 `.txt` 1개. 한 줄에 얼굴 1개:

```
0 <center_x> <center_y> <width> <height>
```

- `0` = face 클래스 id
- 좌표 4개는 모두 이미지 크기로 나눈 0~1 정규화 값

## 이미지와 라벨

실존 인물 얼굴 사진은 초상권 때문에 저장소에서 뺐습니다(2026-11-17). 학습하려면 위 구조대로 `images/`와 `labels/`를 로컬에 직접 넣습니다. 두 폴더는 `.gitignore`에 들어 있습니다.

# OpenAI Image CLI

사람은 읽기 쉬운 명령을 쓰고, 에이전트는 짧은 명령을 쓰도록 설계한 이미지 생성 CLI입니다.

- 긴 명령: `openai-image`
- 짧은 별칭: `oi`
- 기본 생성 방식: `openai-image "prompt"`
- 기본 품질 전략: `--profile best`

기본값은 최고 성능 우선입니다.

- 프로필: `best`
- 모델: `gpt-image-1.5`
- 품질: `high`
- 크기: `auto`
- 스타일: `natural`

## 설치

```bash
cd "/Users/cheon/Desktop/Projects/ai-agent-news/image generator cli"
python3 -m pip install -e .
```

설치 후 사용 가능한 명령:

- `openai-image`
- `oi`
- `nanobanana2`  (호환용)

설치 없이도 프로젝트 루트에서 아래 파일을 직접 실행할 수 있습니다.

- `./openai-image`
- `./oi`

## 필수 환경 변수

```bash
export OPENAI_API_KEY=...
```

선택 환경 변수:

```bash
export IMAGE_GEN_PROFILE="best"
export IMAGE_GEN_MODEL="gpt-image-1.5"
export IMAGE_GEN_OUTPUT_DIR="output"
export IMAGE_GEN_OUTPUT_FORMAT="png"
```

## 명령 구조

### 1. 가장 쉬운 생성

```bash
openai-image "High-end AI news homepage hero, no text, wide composition"
```

짧은 버전:

```bash
oi "High-end AI news homepage hero, no text, wide composition"
```

### 2. 명시적 생성 서브커맨드

```bash
openai-image gen "Premium product photo of a matte black bottle"
```

### 3. 사용 가능한 모델 보기

```bash
openai-image models
```

JSON으로 보기:

```bash
openai-image models --json
```

### 4. 현재 환경 확인

```bash
openai-image check
```

JSON으로 보기:

```bash
openai-image check --json
```

## 추천 사용법

### 최고 성능으로 바로 생성

```bash
openai-image "Luxury fashion campaign portrait, cinematic lighting, shallow depth of field"
```

### 가로 비율로 생성

```bash
openai-image "AI newsroom hero image, negative space for headline" --shape landscape
```

### 투명 배경

```bash
openai-image "Minimal 3D cloud icon" --transparent
```

### 여러 장 생성

```bash
openai-image "Futuristic AI newsroom, ultra clean, cinematic lighting" -n 3
```

### 최종 전송 프롬프트 확인

```bash
openai-image "Luxury travel campaign image of a private island at sunset" --show-prompt
```

### 프롬프트를 원문 그대로 보내기

```bash
openai-image "simple blue icon of a cloud" --raw-prompt
```

### JSON 출력으로 에이전트 연동

```bash
openai-image "High-end AI news homepage hero" --json
```

## 프로필

- `best`: 최고 품질 기본값. 가장 먼저 써야 하는 옵션.
- `balanced`: 품질과 비용 균형.
- `fast`: 더 빠르고 저렴한 생성.
- `chatgpt`: ChatGPT 이미지 모델 기반 동작.

예시:

```bash
openai-image "App onboarding illustration" --profile fast
```

## 모델 선택

2026년 4월 2일 기준 OpenAI 공식 모델 목록의 이미지 모델은 다음과 같습니다.

- `gpt-image-1.5`: state-of-the-art 이미지 생성 모델. 최고 성능 추천.
- `chatgpt-image-latest`: ChatGPT에서 쓰는 이미지 모델.
- `gpt-image-1`: 이전 세대 GPT Image 모델.
- `gpt-image-1-mini`: 더 저렴한 GPT Image 1 계열 모델.
- `dall-e-3`: deprecated.
- `dall-e-2`: deprecated.

실무 권장:

- 최고 품질: `gpt-image-1.5`
- 비용/속도 우선: `gpt-image-1-mini`
- ChatGPT와 유사한 이미지 동작: `chatgpt-image-latest`
- 레거시 호환: `gpt-image-1`, `dall-e-3`, `dall-e-2`

## 에이전트용 예시

```bash
/Users/cheon/Desktop/Projects/ai-agent-news/image\ generator\ cli/oi \
  "High-end AI news homepage hero, wide composition, negative space for headline, no text" \
  --json
```

## 공식 문서

- [OpenAI Image generation guide](https://developers.openai.com/api/docs/guides/image-generation)
- [OpenAI All models](https://developers.openai.com/api/docs/models/all)

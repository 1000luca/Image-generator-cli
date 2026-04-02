from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import openai
from openai import OpenAI


ROOT_PROG = "openai-image"
DEFAULT_OUTPUT_DIR = Path("output")
PROMPT_STDIN_SENTINEL = "-"
DEFAULT_PROFILE = os.getenv("IMAGE_GEN_PROFILE", "best")
DEFAULT_MODEL = os.getenv("IMAGE_GEN_MODEL", "gpt-image-1.5")
DEFAULT_SIZE = os.getenv("IMAGE_GEN_SIZE", "auto")
DEFAULT_QUALITY = os.getenv("IMAGE_GEN_QUALITY", "high")
DEFAULT_STYLE = os.getenv("IMAGE_GEN_STYLE", "natural")
DEFAULT_BACKGROUND = os.getenv("IMAGE_GEN_BACKGROUND", "auto")
DEFAULT_OUTPUT_FORMAT = os.getenv("IMAGE_GEN_OUTPUT_FORMAT", "png")

PROMPT_TEMPLATE = """Create a single polished, high-quality image.

Follow the user's request precisely.
Prioritize strong composition, coherent lighting, clean materials and textures, and premium visual polish.
Do not add text unless the user explicitly asks for it.
Do not add watermarks, logos, signatures, borders, or collage layouts unless requested.
Avoid clutter, malformed anatomy, awkward hands, distorted perspective, oversharpening, and low-quality artifacts.

User request:
{prompt}
"""

OFFICIAL_MODELS_URL = "https://developers.openai.com/api/docs/models/all"
IMAGE_GUIDE_URL = "https://developers.openai.com/api/docs/guides/image-generation"


@dataclass(frozen=True)
class ModelInfo:
    model_id: str
    label: str
    summary: str
    status: str
    recommended_for: str


@dataclass(frozen=True)
class Profile:
    name: str
    model: str
    quality: str
    size: str
    style: str | None
    background: str | None
    summary: str


SUPPORTED_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(
        model_id="gpt-image-1.5",
        label="GPT Image 1.5",
        summary="State-of-the-art image generation model.",
        status="recommended",
        recommended_for="Best quality and strongest default choice.",
    ),
    ModelInfo(
        model_id="chatgpt-image-latest",
        label="ChatGPT Image Latest",
        summary="Image model used in ChatGPT.",
        status="specialized",
        recommended_for="When you want ChatGPT-style image behavior in API form.",
    ),
    ModelInfo(
        model_id="gpt-image-1",
        label="GPT Image 1",
        summary="Previous image generation model.",
        status="previous",
        recommended_for="Compatibility with older GPT Image 1 workflows.",
    ),
    ModelInfo(
        model_id="gpt-image-1-mini",
        label="GPT Image 1 Mini",
        summary="Cost-efficient version of GPT Image 1.",
        status="budget",
        recommended_for="Lower-cost or higher-throughput generation.",
    ),
    ModelInfo(
        model_id="dall-e-3",
        label="DALL-E 3",
        summary="Previous generation image generation model.",
        status="deprecated",
        recommended_for="Legacy compatibility only.",
    ),
    ModelInfo(
        model_id="dall-e-2",
        label="DALL-E 2",
        summary="First OpenAI image generation model.",
        status="deprecated",
        recommended_for="Legacy compatibility only.",
    ),
)

MODEL_INDEX = {item.model_id: item for item in SUPPORTED_MODELS}

PROFILES: dict[str, Profile] = {
    "best": Profile(
        name="best",
        model="gpt-image-1.5",
        quality="high",
        size="auto",
        style="natural",
        background="auto",
        summary="Highest quality default. Best first choice.",
    ),
    "balanced": Profile(
        name="balanced",
        model="gpt-image-1.5",
        quality="medium",
        size="auto",
        style="natural",
        background="auto",
        summary="Good quality with slightly less cost/latency.",
    ),
    "fast": Profile(
        name="fast",
        model="gpt-image-1-mini",
        quality="medium",
        size="auto",
        style="natural",
        background="auto",
        summary="Faster and cheaper than the best profile.",
    ),
    "chatgpt": Profile(
        name="chatgpt",
        model="chatgpt-image-latest",
        quality="high",
        size="auto",
        style="natural",
        background="auto",
        summary="Use the ChatGPT image model in API workflows.",
    ),
}

SHAPE_TO_SIZE = {
    "auto": "auto",
    "square": "1024x1024",
    "landscape": "1536x1024",
    "portrait": "1024x1536",
}


@dataclass
class GenerationResult:
    paths: list[Path]
    prompt: str
    final_prompt: str
    profile: str
    model: str
    size: str | None
    quality: str | None
    background: str | None
    style: str | None
    created_at: str
    revised_prompt: str | None


def slugify(value: str, max_length: int = 60) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    if not normalized:
        normalized = "image"
    return normalized[:max_length].rstrip("-") or "image"


def read_prompt(raw_prompt: str | None) -> str:
    if raw_prompt == PROMPT_STDIN_SENTINEL:
        prompt = sys.stdin.read()
    else:
        prompt = raw_prompt or ""

    prompt = prompt.strip()
    if not prompt:
        raise SystemExit(
            "No prompt provided. Pass text as an argument or use '-' with stdin."
        )
    return prompt


def build_output_path(
    output_dir: Path,
    prompt: str,
    filename: str | None,
    output_format: str | None,
) -> Path:
    if filename:
        return output_dir / filename

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = slugify(prompt)
    extension = (output_format or "png").lower()
    return output_dir / f"{timestamp}-{slug}.{extension}"


def enhance_prompt(prompt: str, raw_prompt: bool) -> str:
    if raw_prompt:
        return prompt
    return PROMPT_TEMPLATE.format(prompt=prompt)


def decode_image_bytes(image_item: object) -> bytes:
    b64_data = getattr(image_item, "b64_json", None)
    if b64_data:
        return base64.b64decode(b64_data)

    raise SystemExit("The image API response did not contain inline image bytes.")


def maybe_open_file(path: Path) -> None:
    if sys.platform != "darwin":
        raise SystemExit("--open is currently supported only on macOS.")
    result = subprocess.run(["open", str(path)], check=False)
    if result.returncode != 0:
        raise SystemExit(f"Failed to open generated image: {path}")


def mask_secret(secret: str) -> str:
    if len(secret) < 10:
        return "*" * len(secret)
    return f"{secret[:7]}...{secret[-4:]}"


def choose_profile(name: str) -> Profile:
    if name not in PROFILES:
        available = ", ".join(PROFILES)
        raise SystemExit(f"Unknown profile '{name}'. Available profiles: {available}")
    return PROFILES[name]


def resolve_size(shape: str, explicit_size: str | None) -> str | None:
    if explicit_size:
        return explicit_size
    return SHAPE_TO_SIZE.get(shape, "auto")


def build_request_kwargs(args: argparse.Namespace, prompt: str) -> dict[str, object]:
    request: dict[str, object] = {
        "model": args.model,
        "prompt": prompt,
        "n": args.count,
        "response_format": "b64_json",
    }

    if args.size:
        request["size"] = args.size
    if args.quality:
        request["quality"] = args.quality
    if args.background:
        request["background"] = args.background
    if args.style:
        request["style"] = args.style
    if args.output_format:
        request["output_format"] = args.output_format

    return request


def apply_profile_defaults(args: argparse.Namespace) -> argparse.Namespace:
    profile = choose_profile(args.profile)

    if args.model is None:
        args.model = profile.model
    if args.quality is None:
        args.quality = profile.quality
    if args.style is None:
        args.style = profile.style
    if args.background is None:
        args.background = profile.background
    args.size = resolve_size(args.shape, args.size or profile.size)

    if args.transparent:
        args.background = "transparent"

    return args


def generate_image(args: argparse.Namespace) -> GenerationResult:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set.")
    if args.filename and args.count > 1:
        raise SystemExit("--filename can only be used when --count is 1.")

    args = apply_profile_defaults(args)
    prompt = read_prompt(args.prompt)
    final_prompt = enhance_prompt(prompt, raw_prompt=args.raw_prompt)
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI()
    response = client.images.generate(**build_request_kwargs(args, final_prompt))

    if not getattr(response, "data", None):
        raise SystemExit("The image API returned no results.")

    output_paths: list[Path] = []
    for index, item in enumerate(response.data, start=1):
        output_path = build_output_path(
            output_dir,
            prompt if args.count == 1 else f"{prompt}-{index}",
            args.filename,
            args.output_format,
        )
        output_path.write_bytes(decode_image_bytes(item))
        output_paths.append(output_path.resolve())

    if args.open and output_paths:
        maybe_open_file(output_paths[0])

    return GenerationResult(
        paths=output_paths,
        prompt=prompt,
        final_prompt=final_prompt,
        profile=args.profile,
        model=args.model,
        size=args.size,
        quality=args.quality,
        background=args.background,
        style=args.style,
        created_at=datetime.now().isoformat(timespec="seconds"),
        revised_prompt=getattr(response.data[0], "revised_prompt", None),
    )


def print_generation_result(result: GenerationResult, as_json: bool) -> None:
    payload = {
        "paths": [str(path) for path in result.paths],
        "prompt": result.prompt,
        "final_prompt": result.final_prompt,
        "profile": result.profile,
        "model": result.model,
        "size": result.size,
        "quality": result.quality,
        "background": result.background,
        "style": result.style,
        "created_at": result.created_at,
        "revised_prompt": result.revised_prompt,
    }

    if as_json:
        json.dump(payload, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    for path in result.paths:
        print(f"saved: {path}")
    print(f"profile: {result.profile}")
    print(f"model: {result.model}")
    print(f"size: {result.size}")
    print(f"quality: {result.quality}")
    if result.revised_prompt:
        print(f"revised_prompt: {result.revised_prompt}")


def print_models(as_json: bool) -> None:
    payload = {
        "recommended_model": "gpt-image-1.5",
        "models": [
            {
                "id": item.model_id,
                "label": item.label,
                "summary": item.summary,
                "status": item.status,
                "recommended_for": item.recommended_for,
            }
            for item in SUPPORTED_MODELS
        ],
        "source": OFFICIAL_MODELS_URL,
    }

    if as_json:
        json.dump(payload, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    print("recommended: gpt-image-1.5")
    for item in SUPPORTED_MODELS:
        print(
            f"{item.model_id} | {item.status} | {item.summary} | {item.recommended_for}"
        )
    print(f"source: {OFFICIAL_MODELS_URL}")


def print_check(as_json: bool) -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    payload = {
        "openai_api_key_present": bool(api_key),
        "openai_api_key_masked": mask_secret(api_key) if api_key else None,
        "default_profile": DEFAULT_PROFILE,
        "default_model_env": os.getenv("IMAGE_GEN_MODEL"),
        "effective_default_model": DEFAULT_MODEL,
        "openai_package_version": getattr(openai, "__version__", None),
        "image_models_source": OFFICIAL_MODELS_URL,
        "image_guide_source": IMAGE_GUIDE_URL,
    }

    if as_json:
        json.dump(payload, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    print(f"OPENAI_API_KEY: {'present' if api_key else 'missing'}")
    if api_key:
        print(f"masked_key: {mask_secret(api_key)}")
    print(f"default_profile: {DEFAULT_PROFILE}")
    print(f"effective_default_model: {DEFAULT_MODEL}")
    print(f"openai_package_version: {getattr(openai, '__version__', 'unknown')}")
    print(f"models_source: {OFFICIAL_MODELS_URL}")


def add_generation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Prompt text, or '-' to read the prompt from stdin.",
    )
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES.keys()),
        default=DEFAULT_PROFILE,
        help="Generation preset. 'best' is the default and highest-quality option.",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=os.getenv("IMAGE_GEN_MODEL"),
        help="Override the model selected by the profile.",
    )
    parser.add_argument(
        "--shape",
        choices=tuple(SHAPE_TO_SIZE.keys()),
        default="auto",
        help="Convenience size preset. Ignored when --size is set explicitly.",
    )
    parser.add_argument(
        "--size",
        default=os.getenv("IMAGE_GEN_SIZE"),
        help="Explicit image size, for example auto, 1024x1024, or 1536x1024.",
    )
    parser.add_argument(
        "--quality",
        default=os.getenv("IMAGE_GEN_QUALITY"),
        help="Quality override. If omitted, the selected profile decides.",
    )
    parser.add_argument(
        "--background",
        default=os.getenv("IMAGE_GEN_BACKGROUND"),
        help="Background mode, for example auto, opaque, or transparent.",
    )
    parser.add_argument(
        "--transparent",
        action="store_true",
        help="Shortcut for --background transparent.",
    )
    parser.add_argument(
        "--style",
        default=os.getenv("IMAGE_GEN_STYLE"),
        help="Style override, for example vivid or natural.",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        default=DEFAULT_OUTPUT_FORMAT,
        help="Output file format, for example png, webp, or jpeg.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("IMAGE_GEN_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="Directory where generated images are written.",
    )
    parser.add_argument(
        "--filename",
        help="Explicit output filename for a single image. Use only when count is 1.",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=1,
        help="Number of images to generate.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the first generated image after saving it (macOS only).",
    )
    parser.add_argument(
        "--raw-prompt",
        action="store_true",
        help="Send the prompt as-is without automatic quality enhancement.",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Print the final prompt that was sent to OpenAI.",
    )


def build_root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=ROOT_PROG,
        description=(
            "Generate high-quality images with OpenAI. "
            "Use a prompt directly or use subcommands like 'models' and 'check'."
        ),
    )
    add_generation_arguments(parser)
    return parser


def build_gen_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{ROOT_PROG} gen",
        description="Explicit generation subcommand. Equivalent to using the root command with a prompt.",
    )
    add_generation_arguments(parser)
    return parser


def build_models_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{ROOT_PROG} models",
        description="Show officially listed OpenAI image models.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def build_check_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{ROOT_PROG} check",
        description="Check local environment readiness for image generation.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def run_generation_from_args(args: argparse.Namespace) -> None:
    result = generate_image(args)
    if args.show_prompt and not args.json:
        print(result.final_prompt)
    print_generation_result(result, as_json=args.json)


def dispatch(argv: list[str]) -> None:
    subcommands = {"gen", "models", "check"}

    if argv and argv[0] in subcommands:
        command = argv[0]
        rest = argv[1:]
        if command == "gen":
            args = build_gen_parser().parse_args(rest)
            run_generation_from_args(args)
            return
        if command == "models":
            args = build_models_parser().parse_args(rest)
            print_models(as_json=args.json)
            return
        if command == "check":
            args = build_check_parser().parse_args(rest)
            print_check(as_json=args.json)
            return

    args = build_root_parser().parse_args(argv)
    run_generation_from_args(args)


def main() -> None:
    dispatch(sys.argv[1:])


if __name__ == "__main__":
    main()

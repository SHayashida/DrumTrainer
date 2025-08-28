from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich import box
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table


console = Console()
app = typer.Typer(help="Drum practice backing track CLI (local MVP)")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="%H:%M:%S",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def normalize_song_name(path: Path) -> str:
    return path.stem.replace(" ", "_")


def ffmpeg_convert_to_wav(input_path: Path, out_wav: Path) -> None:
    try:
        import ffmpeg  # type: ignore
    except Exception as e:
        raise RuntimeError("ffmpeg-python が必要です。`pip install ffmpeg-python` と FFmpeg 本体をインストールしてください。") from e

    stream = (
        ffmpeg.input(str(input_path))
        .output(
            str(out_wav),
            acodec="pcm_s16le",
            ac=2,
            ar=44100,
            loglevel="error",
        )
        .overwrite_output()
    )
    stream.run()


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def run_demucs(input_wav: Path, temp_out_dir: Path, model: str = "htdemucs") -> None:
    ensure_dir(temp_out_dir)
    demucs_bin = which("demucs")
    if demucs_bin is not None:
        cmd = [demucs_bin, "-n", model, "-o", str(temp_out_dir), str(input_wav)]
    else:
        cmd = [sys.executable, "-m", "demucs", "-n", model, "-o", str(temp_out_dir), str(input_wav)]

    logging.info("[demucs] 実行: %s", " ".join(cmd))
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"demucs が失敗しました (returncode={proc.returncode})")


def find_stems_dir(temp_out_dir: Path, song_name: str) -> Path:
    candidates: List[Path] = []
    for p in temp_out_dir.rglob("vocals.wav"):
        if p.parent.name.lower() == song_name.lower():
            candidates.append(p.parent)
    if not candidates:
        # fallback: pick any directory that has all stems
        for parent in temp_out_dir.rglob("*"):
            if parent.is_dir():
                stems = [parent / n for n in ["vocals.wav", "drums.wav", "bass.wav", "other.wav"]]
                if all(s.exists() for s in stems):
                    candidates.append(parent)
    if not candidates:
        raise FileNotFoundError("Demucsの出力ディレクトリが見つかりませんでした。")
    # 最初の候補を使用
    return candidates[0]


def copy_stems(src_dir: Path, dest_dir: Path) -> None:
    ensure_dir(dest_dir)
    for stem in ["vocals.wav", "drums.wav", "bass.wav", "other.wav"]:
        s = src_dir / stem
        if not s.exists():
            raise FileNotFoundError(f"必須stemがありません: {s}")
        shutil.copy2(s, dest_dir / stem)


@app.command()
def separate(
    song: Path = typer.Argument(..., exists=True, readable=True, help="入力オーディオ(.wav/.mp3/.m4a 等)"),
    model: str = typer.Option("htdemucs", "--model", help="Demucsモデル名"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="出力先 (未指定は ./outputs/<曲名>)"),
    verbose: bool = typer.Option(False, "--verbose", help="詳細ログ"),
) -> None:
    """Demucsで stems を分離し、規定の出力構成に整える。"""
    setup_logging(verbose)
    try:
        song_name = normalize_song_name(song)
        dest_root = out_dir if out_dir is not None else Path("outputs") / song_name
        ensure_dir(dest_root)

        mix_wav = dest_root / "mix.wav"
        logging.info("入力をWAVに正規化変換中 -> %s", mix_wav)
        ffmpeg_convert_to_wav(song, mix_wav)

        temp_out = dest_root / "_demucs_out"
        run_demucs(mix_wav, temp_out, model=model)

        stems_src = find_stems_dir(temp_out, song_name)
        logging.info("Demucs出力: %s", stems_src)
        copy_stems(stems_src, dest_root)

        try:
            shutil.rmtree(temp_out, ignore_errors=True)
        except Exception:
            pass

        logging.info("分離完了: %s", dest_root)
        table = Table(title="Separated Stems", box=box.SIMPLE)
        table.add_column("File")
        for n in ["mix.wav", "vocals.wav", "drums.wav", "bass.wav", "other.wav"]:
            table.add_row(str((dest_root / n).resolve()))
        console.print(table)
    except Exception as e:
        logging.exception("separate でエラーが発生しました")
        raise typer.Exit(code=1) from e


@app.command()
def analyze(
    mix_path: Path = typer.Argument(..., exists=True, readable=True, help="mix.wav のパス"),
    verbose: bool = typer.Option(False, "--verbose", help="詳細ログ"),
) -> None:
    """BPM と beat times を推定し metadata.json に保存する。"""
    setup_logging(verbose)
    try:
        import librosa  # type: ignore
        import numpy as np  # type: ignore

        y, sr = librosa.load(str(mix_path), sr=None, mono=True)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        times = librosa.frames_to_time(beats, sr=sr)
        times_list = [float(f"{t:.6f}") for t in times.tolist()]

        meta = {"bpm": float(f"{tempo:.4f}"), "beats": times_list}
        meta_path = mix_path.parent / "metadata.json"
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        table = Table(title="Analyze Result", box=box.SIMPLE)
        table.add_column("Key")
        table.add_column("Value")
        table.add_row("bpm", str(meta["bpm"]))
        table.add_row("beats", f"{len(times_list)} positions")
        console.print(table)
        console.print(f"metadata.json -> {meta_path.resolve()}")
    except Exception as e:
        logging.exception("analyze でエラーが発生しました")
        raise typer.Exit(code=1) from e


def _load_seg(path: Path):
    from pydub import AudioSegment  # type: ignore

    seg = AudioSegment.from_file(str(path))
    return seg.set_channels(2)


def _longest_duration_ms(segs):
    return max(int(s.duration_seconds * 1000) for s in segs)


def _make_click_sample(sample_rate: int = 44100, level_db: float = -6.0):
    from pydub.generators import WhiteNoise  # type: ignore

    click = WhiteNoise().to_audio_segment(duration=20).set_frame_rate(sample_rate)
    click = click.fade_out(15)
    click = click - max(0.0, -level_db) if level_db < 0 else click + level_db
    return click


@app.command("make-backing")
def make_backing(
    stems_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="stemsが入ったディレクトリ"),
    auto_bpm: bool = typer.Option(False, "--auto-bpm", help="mix.wav から自動推定"),
    bpm: Optional[float] = typer.Option(None, "--bpm", help="固定BPM (auto指定なし時)"),
    with_click: bool = typer.Option(False, "--with-click", help="クリック音を重ねる"),
    drum_gain: float = typer.Option(-120.0, "--drum-gain", help="ドラムゲイン(dB, 負値で減衰)"),
    mp3: bool = typer.Option(False, "--mp3", help="MP3も書き出す"),
    verbose: bool = typer.Option(False, "--verbose", help="詳細ログ"),
) -> None:
    """ドラムをミュート/減衰し、必要ならクリックを重ねて backing を生成。"""
    setup_logging(verbose)
    try:
        from pydub import AudioSegment  # type: ignore

        required = ["vocals.wav", "drums.wav", "bass.wav", "other.wav", "mix.wav"]
        for n in required:
            if not (stems_dir / n).exists():
                raise FileNotFoundError(f"必要ファイルがありません: {stems_dir / n}")

        vocals = _load_seg(stems_dir / "vocals.wav")
        drums = _load_seg(stems_dir / "drums.wav")
        bass = _load_seg(stems_dir / "bass.wav")
        other = _load_seg(stems_dir / "other.wav")
        mix = _load_seg(stems_dir / "mix.wav")

        frame_rate = mix.frame_rate
        max_len = _longest_duration_ms([vocals, drums, bass, other, mix])
        base = AudioSegment.silent(duration=max_len, frame_rate=frame_rate).set_channels(2)

        if drum_gain is not None:
            drums = drums + drum_gain

        backing = base.overlay(vocals)
        backing = backing.overlay(bass)
        backing = backing.overlay(other)
        backing = backing.overlay(drums)

        beats_sec: List[float] = []
        if with_click:
            if auto_bpm:
                meta_path = stems_dir / "metadata.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    beats_sec = [float(t) for t in meta.get("beats", [])]
                else:
                    # オンザフライ推定
                    import librosa  # type: ignore

                    y, sr = librosa.load(str(stems_dir / "mix.wav"), sr=None, mono=True)
                    _, beats = librosa.beat.beat_track(y=y, sr=sr)
                    beats_sec = [float(t) for t in librosa.frames_to_time(beats, sr=sr).tolist()]
            elif bpm and bpm > 0:
                step = 60.0 / bpm
                total = max_len / 1000.0
                t = 0.0
                while t <= total:
                    beats_sec.append(round(t, 6))
                    t += step

            if beats_sec:
                click = _make_click_sample(sample_rate=frame_rate, level_db=-6.0)
                for t in beats_sec:
                    pos = int(t * 1000)
                    if 0 <= pos < max_len:
                        backing = backing.overlay(click, position=pos)

        # ラウドネス整形 (最大値を -1dBFS 付近に)
        gain = -1.0 - backing.max_dBFS if backing.max_dBFS != float("-inf") else 0.0
        backing = backing.apply_gain(gain)

        out_wav = stems_dir / "backing.wav"
        backing.export(str(out_wav), format="wav")
        logging.info("backing.wav -> %s", out_wav.resolve())

        if mp3:
            out_mp3 = stems_dir / "backing.mp3"
            backing.export(str(out_mp3), format="mp3")
            logging.info("backing.mp3 -> %s", out_mp3.resolve())

        table = Table(title="Backing Generated", box=box.SIMPLE)
        table.add_column("File")
        table.add_row(str(out_wav.resolve()))
        if mp3:
            table.add_row(str((stems_dir / "backing.mp3").resolve()))
        console.print(table)
    except Exception as e:
        logging.exception("make-backing でエラーが発生しました")
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    app()


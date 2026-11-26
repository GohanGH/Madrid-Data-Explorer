"""Scoped progress indicator using the local IGN silhouette."""
from contextlib import contextmanager
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st


@lru_cache(maxsize=1)
def silhouette():
    return (Path(__file__).resolve().parent / "demo_data" / "madrid_silueta.svg").read_text(encoding="utf-8")


@contextmanager
def loading(label):
    slot = st.empty()
    slot.html(f"""
        <style>
        .mde-progress {{display:flex;align-items:center;min-height:2rem;color:#49D5B3}}
        .mde-progress svg {{width:2rem;height:2rem;transform-origin:50% 50%;
                           animation:mde-turn 2.4s linear infinite}}
        @keyframes mde-turn {{to {{transform:rotate(360deg)}}}}
        @media (prefers-reduced-motion:reduce) {{.mde-progress svg {{animation:none}}}}
        </style>
        <div class="mde-progress" role="status" aria-label="{escape(label, quote=True)}">{silhouette()}</div>
    """)
    try:
        yield
    finally:
        slot.empty()

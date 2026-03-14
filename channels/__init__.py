# -*- coding: utf-8 -*-
"""多通道适配器：将各渠道入参标准化后调用桥接层，再按渠道格式回写。"""
from channels.base import ChannelAdapter, InboundEvent, AdapterRegistry

__all__ = ["ChannelAdapter", "InboundEvent", "AdapterRegistry"]

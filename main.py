from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.provider as ProviderRequest
from astrbot.api.all import *

import os
import json
import time
from typing import Optional, Dict, Any
import jieba

@register("memory_ye", "gameswu", "这是一个用于为小夜提供记忆功能的插件。", "0.1.0", "https://github.com/gameswu/memory_ye")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.max_memories = config.get("max memories", 100)

    async def initialize(self):
        # 在两级父目录下创建一个名为 memory_ye 的文件夹用于存储数据
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "memory_ye")
        os.makedirs(self.data_dir, exist_ok=True)

    async def _add_memory(self, user_id: str, content: str, importance: int, valid_time: int):
        """
        添加记忆
        
        Args:
            user_id (str): 用户ID
            content (str): 记忆内容
            importance (int): 重要性等级
            valid_time (int): 记忆有效时间（秒）

        Returns:
            int: 记忆ID
        """
        # 检查是否存在该用户的记忆文件
        memory_file = os.path.join(self.data_dir, f"{user_id}.json")
        if not os.path.exists(memory_file):
            # 如果不存在，则创建一个新的记忆文件
            with open(memory_file, "w") as f:
                json.dump({"user_id": user_id, "count": 0, "memory": []}, f)
        
        # 读取现有的记忆
        with open(memory_file, "r") as f:
            data = json.load(f)
            
        # 获取当前时间戳
        current_time = int(time.time())
        
        # 创建新的记忆
        # 使用时间戳+随机数确保ID唯一性
        import random
        unique_id = int(f"{current_time}{random.randint(1000, 9999)}")
        
        new_memory = {
            "id": unique_id,
            "content": content,
            "time": current_time,
            "importance": importance,
            "last_access_time": current_time,
            "valid_time": valid_time
        }
        
        # 添加新记忆
        if "memory" not in data:
            data["memory"] = []
        data["memory"].append(new_memory)
        # 更新count为当前记忆数量
        data["count"] = len(data["memory"])
        
        # 处理记忆容量限制
        max_memories = self.max_memories  # 使用类变量中的最大记忆数量
        if len(data["memory"]) > max_memories:
            # 1. 删除所有超过有效时间的记忆
            data["memory"] = [
                m for m in data["memory"] 
                if (current_time - m["last_access_time"]) < m["valid_time"]
            ]
            
            # 如果删除过期记忆后仍然超过限制
            if len(data["memory"]) > max_memories:
                # 2,3,4. 按照重要性、上次访问时间和创建时间排序
                data["memory"].sort(key=lambda m: (
                    m["importance"],
                    m["last_access_time"],
                    m["time"]
                ))
                # 保留最重要/最近访问/最新创建的记忆
                data["memory"] = data["memory"][-max_memories:]
        
        # 保存更新后的记忆数据
        with open(memory_file, "w") as f:
            json.dump(data, f, indent=2)
        
        return unique_id
    
    async def _search_memory(self, user_id: str, keyword: str):
        """
        模糊搜索记忆
        
        Args:
            user_id (str): 用户ID
            keyword (str): 关键词

        Returns:
            List[Dict]: 匹配的记忆ID和匹配度列表
        """
        # 检查是否存在该用户的记忆文件
        memory_file = os.path.join(self.data_dir, f"{user_id}.json")
        if not os.path.exists(memory_file):
            return []
        
        # 读取现有的记忆
        with open(memory_file, "r") as f:
            data = json.load(f)
        
        # 分词处理关键词
        keyword_words = set(jieba.cut(keyword))
        
        # 计算每条记忆的匹配度
        memory_scores = []
        for memory in data.get("memory", []):
            # 对记忆内容分词
            memory_words = set(jieba.cut(memory["content"]))
            
            # 计算匹配度 (交集词数 / 关键词总数)
            if keyword_words:
                common_words = memory_words.intersection(keyword_words)
                score = len(common_words) / len(keyword_words)
                
                # 只返回有匹配的记忆
                if score > 0:
                    memory_scores.append({
                        "id": memory["id"],
                        "score": score,
                        "content": memory["content"],
                        "importance": memory["importance"]
                    })
        
        # 按匹配度降序排序
        memory_scores.sort(key=lambda x: x["score"], reverse=True)
        
        return memory_scores
    
    async def _update_memory(self, user_id: str, id: int, content: str, importance: int):
        """
        更新记忆
        
        Args:
            user_id (str): 用户ID
            id (int): 记忆ID
            content (str): 新的记忆内容
            importance (int): 新的记忆重要性等级

        Returns:
            bool: 是否更新成功
        """
        # 检查是否存在该用户的记忆文件
        memory_file = os.path.join(self.data_dir, f"{user_id}.json")
        if not os.path.exists(memory_file):
            return False
        
        # 读取现有的记忆
        with open(memory_file, "r") as f:
            data = json.load(f)
        
        # 查找并更新指定的记忆
        for memory in data.get("memory", []):
            if memory["id"] == id:
                memory["content"] = content
                memory["importance"] = importance
                break
        else:
            return False
        
        # 保存更新后的记忆数据
        with open(memory_file, "w") as f:
            json.dump(data, f, indent=2)
        
        return True
    
    async def _delete_memory(self, user_id: str, id: int):
        """
        删除记忆
        Args:
            user_id (str): 用户ID
            id (int): 记忆ID
        Returns:
            bool: 是否删除成功
        """
        # 检查是否存在该用户的记忆文件
        memory_file = os.path.join(self.data_dir, f"{user_id}.json")
        if not os.path.exists(memory_file):
            return False
        
        # 读取现有的记忆
        with open(memory_file, "r") as f:
            data = json.load(f)
        
        # 查找并删除指定的记忆
        for i, memory in enumerate(data.get("memory", [])):
            if memory["id"] == id:
                del data["memory"][i]
                # 更新count为当前记忆数量
                data["count"] = len(data["memory"])
                break
        else:
            return False
        
        # 保存更新后的记忆数据
        with open(memory_file, "w") as f:
            json.dump(data, f, indent=2)
        
        return True
    
    @filter.llm_tool(name="search_memory")
    async def search_memory(self, event: AstrMessageEvent, keyword: str):
        """
        根据关键词keyword搜索匹配的记忆
        
        Args:
            keyword(string): 搜索匹配的关键词
        """
        user_id = event.get_sender_id()
        if not user_id:
            return "无法获取用户ID。"
        memories = await self._search_memory(user_id, keyword)
        
        if not memories:
            return "没有找到相关的记忆。"
        
        response = "找到以下相关记忆：\n"
        for memory in memories:
            response += f"记忆ID: {memory['id']}, 匹配度: {memory['score']:.2f}, 内容: {memory['content']}, 重要性: {memory['importance']}\n"
        
        return response
    
    @filter.llm_tool(name="add_memory")
    async def add_memory(self, event: AstrMessageEvent, content: str, importance: int, valid_time: int):
        """
        添加新的记忆内容，包括内容、重要性等级和有效时间（秒）
        
        Args:
            content(string): 记忆内容
            importance(number): 重要性等级
            valid_time(number): 记忆有效时间（秒）
        """
        user_id = event.get_sender_id()
        if not user_id:
            return "无法获取用户ID。"
        
        id = await self._add_memory(user_id, content, importance, valid_time)
        
        return f"记忆添加成功，ID: {id}， 内容: {content}，重要性: {importance}，有效时间: {valid_time}秒。"
    
    @filter.llm_tool(name="update_memory")
    async def update_memory(self, event: AstrMessageEvent, id: int, content: str, importance: int):
        """
        更新指定ID的记忆内容，包括新的内容和重要性等级
        
        Args:
            id(number): 记忆ID
            content(string): 新的记忆内容
            importance(number): 新的记忆重要性等级
        """
        user_id = event.get_sender_id()
        if not user_id:
            return "无法获取用户ID。"
        
        success = await self._update_memory(user_id, id, content, importance)
        
        if success:
            return f"记忆更新成功，ID: {id}，新的内容: {content}，新的重要性: {importance}。"
        else:
            return f"未找到ID为{id}的记忆。"

    @filter.permission_type(filter.PermissionType.ADMIN)     
    @filter.command("增加记忆")
    async def add_memory_command(self, event: AstrMessageEvent, user_id: str, content: str, importance: int = 2, valid_time: int = 86400):
        """
        命令行接口，增加记忆
        """
        if not user_id:
            message = "无法获取用户ID。"
            logger.info(message)
        
        id = await self._add_memory(user_id, content, importance, valid_time)
        
        message = f"记忆添加成功，ID: {id}， 内容: {content}，重要性: {importance}，有效时间: {valid_time}秒。"
        logger.info(message)
    
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("删除记忆")
    async def delete_memory_command(self, event: AstrMessageEvent, user_id: str, id: int):
        """
        命令行接口，删除记忆
        """
        if not user_id:
            message = "无法获取用户ID。"
            logger.info(message)
        
        success = await self._delete_memory(user_id, id)
        
        if success:
            message = f"记忆删除成功，ID: {id}。"
        else:
            message = f"未找到ID为{id}的记忆。"
        
        logger.info(message)
        
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("修改记忆")
    async def update_memory_command(self, event: AstrMessageEvent, user_id: str, id: int, content: str, importance: int = 2):
        """
        命令行接口，更新记忆
        """
        if not user_id:
            message = "无法获取用户ID。"
            logger.info(message)
        
        success = await self._update_memory(user_id, id, content, importance)
        
        if success:
            message = f"记忆更新成功，ID: {id}，新的内容: {content}，新的重要性: {importance}。"
        else:
            message = f"未找到ID为{id}的记忆。"
        
        logger.info(message)
        
    @filter.command("导出记忆")
    async def export_memory_command(self, event: AstrMessageEvent, keyword: str = None):
        """
        命令行接口，导出记忆
        如果提供了keyword参数，则只导出与该关键词相关的记忆
        """
        user_id = event.get_sender_id()
        if not user_id:
            message = "无法获取用户ID。"
            logger.info(message)
            yield event.plain_result(message)
            
        # 检查是否存在该用户的记忆文件
        memory_file = os.path.join(self.data_dir, f"{user_id}.json")
        if not os.path.exists(memory_file):
            message = "暂时没有记忆。"
            logger.info(message)
            yield event.plain_result(message)
        else:
        
            # 读取现有的记忆
            with open(memory_file, "r") as f:
                data = json.load(f)
        
        # 检查是否有记忆内容
        if not data.get("memory", []):
            message = "暂时没有记忆。"
            logger.info(message)
            yield event.plain_result(message)
        
        memories_to_display = []
        
        # 如果提供了关键词，则使用搜索功能筛选记忆
        if keyword:
            search_results = await self._search_memory(user_id, keyword)
            if not search_results:
                message = f"未找到与关键词'{keyword}'相关的记忆。"
                logger.info(message)
                yield event.plain_result(message)
                
            # 获取匹配的记忆ID列表
            matched_ids = [item["id"] for item in search_results]
            # 筛选原始记忆中匹配的内容
            memories_to_display = [m for m in data.get("memory", []) if m["id"] in matched_ids]
            response = f"用户{user_id}与关键词'{keyword}'相关的记忆内容：\n"
        else:
            # 不提供关键词时，显示所有记忆
            memories_to_display = data.get("memory", [])
            response = f"用户{user_id}导出的所有记忆内容：\n"
        
        for memory in memories_to_display:
            # 将时间戳转换为yyyy-mm-dd hh:mm:ss格式
            formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(memory['time']))
            response += f"ID: {memory['id']}, 时间: {formatted_time}, 内容: {memory['content']}, 重要性: {memory['importance']}\n"
        
        yield event.plain_result(response)

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""

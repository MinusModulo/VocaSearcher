import os
import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime
from sudachipy import dictionary, tokenizer
import logging

class WordDatabaseBuilder:
    def __init__(self, db_name="songs.db"):

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        self.db_name = db_name
        self.db_path = Path(db_name)

        if not self.db_path.exists():
            self.logger.error(f"数据库文件 {db_name} 不存在，请先运行 dbbuilder.py 来创建数据库")
            raise FileNotFoundError(f"数据库文件 {db_name} 不存在")
        
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.mode = tokenizer.Tokenizer.SplitMode.C
        self.word_map = {}
        self.assoc_map = []
        self.tokenizer = dictionary.Dictionary().create()

    def create_tables(self):
        """创建单词相关的表"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lemma TEXT UNIQUE NOT NULL,
                frequency INTEGER DEFAULT 0,
                song_count INTEGER DEFAULT 0
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS word_lyrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER,
                lyric_id INTEGER,
                word_number INTEGER,
                reading_form TEXT,
                surface TEXT,
                FOREIGN KEY (word_id) REFERENCES words(id),
                FOREIGN KEY (lyric_id) REFERENCES lyrics(id)
            )
        """)
        self.conn.commit()
        self.logger.info("单词相关的表已创建或已存在")

    def process_lyric(self, song_id, lyric_id, lyric_text):
        """处理单个歌词，提取单词并存储到数据库"""
        tokens = self.tokenizer.tokenize(lyric_text, self.mode)

        for number, token in enumerate(tokens):
            lemma = token.normalized_form()
            reading_form = token.reading_form()
            if not lemma or re.match(r'^\W+$', lemma):
                continue

            if lemma not in self.word_map:
                self.word_map[lemma] = {
                    'frequency': 0,
                    'song': set()
                }

            self.word_map[lemma]['frequency'] += 1
            self.word_map[lemma]['song'].add(song_id)
            surface_string = ""
            for numb, word in enumerate(tokens):
                if numb != number:
                    surface_string += word.surface()
                else:
                    surface_string += "【" + word.surface() + "】"
            self.assoc_map.append({
                'lyric_id': lyric_id,
                'word': lemma,
                'reading_form': reading_form,
                'surface': surface_string,
                'word_number': number + 1
            })

    def run(self):
        """运行数据库构建流程"""
        try:
            self.create_tables()
            self.logger.info("数据库表创建成功")
        except sqlite3.Error as e:
            self.logger.error(f"数据库错误: {e}")

        self.cursor.execute("SELECT id, song_id, japanese FROM lyrics")
        lyrics = self.cursor.fetchall()
        if not lyrics:
            self.logger.warning("没有找到任何歌词数据")
            return
        self.logger.info(f"共找到 {len(lyrics)} 条歌词数据")

        for lyric_id, song_id, lyric_text in lyrics:
            if (lyric_id % 1000) == 0:
                self.logger.info(f"处理歌词 ID: {lyric_id}，对应歌曲 ID: {song_id}")
            self.process_lyric(song_id, lyric_id, lyric_text)

        self.logger.info("歌词处理完成，开始存储单词数据")

        for lemma, data in self.word_map.items():
            frequency = data['frequency']
            song_count = len(data['song'])
            self.cursor.execute("""
                INSERT OR IGNORE INTO words (lemma, frequency, song_count)
                VALUES (?, ?, ?)
            """, (lemma, frequency, song_count))
            self.word_map[lemma]['id'] = self.cursor.lastrowid
        
        for (number, assoc) in enumerate(self.assoc_map):
            if number % 5000 == 0:
                self.logger.info(f"存储单词关联数据: {number} / {len(self.assoc_map)}")
            self.cursor.execute("""
                INSERT INTO word_lyrics (word_id, lyric_id, word_number, reading_form, surface)
                VALUES (?, ?, ?, ?, ?)
            """, (self.word_map[assoc['word']]['id'], assoc['lyric_id'], assoc['word_number'], assoc['reading_form'], assoc['surface']))
        self.conn.commit()
        self.logger.info("单词数据存储完成")
        self.logger.info("歌词与单词关联数据存储完成")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.logger.info("数据库连接已关闭")

if __name__ == "__main__":
    db_builder = WordDatabaseBuilder()
    db_builder.run()
    db_builder.close()

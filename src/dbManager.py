from pathlib import Path
import logging
import sqlite3
from sudachipy import dictionary, tokenizer

class DBManager:
    def __init__(self, db_dir='../db/songs.db'):
        self.db_path = Path(db_dir)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        self.logger.info(f"连接到数据库: {self.db_path}")

        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.mode = tokenizer.Tokenizer.SplitMode.C
        self.tokenizer = dictionary.Dictionary().create()

    def search_word_by_raw_word(self, raw_word, limit=10, offset=0):
        """根据原始单词搜索单词"""
        try:
            self.cursor.execute("""
                SELECT id, lemma, song_count
                FROM words
                WHERE lemma LIKE ?
                ORDER BY song_count DESC
                LIMIT ? OFFSET ?
            """, ('%' + raw_word + '%', limit, offset))
            results = self.cursor.fetchall()
            return results
        except sqlite3.Error as e:
            self.logger.error(f"搜索单词失败: {str(e)}")
            return None

    def search_word_by_lemma(self, lemma):
        """根据词元搜索单词"""
        try:
            self.cursor.execute("""
                SELECT id
                FROM words
                WHERE lemma = ?
                ORDER BY song_count DESC
            """, (lemma,))
            results = self.cursor.fetchone()[0]
            return results
        except sqlite3.Error as e:
            self.logger.error(f"搜索单词失败: {str(e)}")
            return []
        
    def search_song_by_lyricid(self, lyric_id):
        """根据歌词ID获取歌曲信息"""
        try:
            self.cursor.execute("""
                SELECT song_id
                FROM lyrics
                WHERE id = ?
            """, (lyric_id,))
            result = self.cursor.fetchone()
            if not result:
                self.logger.error(f"未找到对应的歌词行: {lyric_id}")
                return []
            song_id = result[0]
            self.cursor.execute("""
                SELECT id, original_title, singer, upload_date, views, link
                FROM songs
                WHERE id = ?
            """, (song_id,))
            results = self.cursor.fetchone()
            return results
        except sqlite3.Error as e:
            self.logger.error(f"根据歌词ID获取歌曲信息失败: {str(e)}")
            return []

    def get_lyric_by_id(self, lyric_id):
        """根据歌词ID获取歌词行信息"""
        try:
            self.cursor.execute("""
                SELECT id, song_id, line_number, japanese, romaji
                FROM lyrics
                WHERE id = ?
            """, (lyric_id,))
            result = self.cursor.fetchone()
            return result
        except sqlite3.Error as e:
            self.logger.error(f"根据歌词ID获取歌词行失败: {str(e)}")
            return None

    def search_word_lyrics_by_word(self, word, limit=10, offset=0):
        """搜索包含指定单词的关系"""
        word_id = self.search_word_by_lemma(word)
        if not word_id:
            self.logger.error(f"搜索单词失败: 找不到单词 {word}")
            return []
        try:
            self.cursor.execute("""
                SELECT word_id, lyric_id, word_number, reading_form, surface
                FROM word_lyrics
                WHERE word_id = ?
                LIMIT ? OFFSET ?
            """, (word_id, limit, offset))
            results = self.cursor.fetchall()
            return results
        except sqlite3.Error as e:
            self.logger.error(f"搜索单词失败: {str(e)}")
            return []

    def search_songs_by_title(self, song_title, limit=20, offset=0):
        """根据歌曲标题搜索相关单词"""
        try:
            self.cursor.execute("""
                SELECT id, original_title, singer, upload_date, views, link
                FROM songs
                WHERE title LIKE ?
                ORDER BY LENGTH(original_title)
                LIMIT ? OFFSET ?
            """, ('%'+song_title+'%', limit, offset))
            results = self.cursor.fetchall()
            return results
        except sqlite3.Error as e:
            self.logger.error(f"根据歌曲标题搜索单词失败: {str(e)}")
            return []
        
    def search_lyrics_by_songid(self, song_id):
        """根据歌曲ID获取歌词"""
        try:
            self.cursor.execute("""
                SELECT id, line_number, japanese, romaji
                FROM lyrics
                WHERE song_id = ?
                ORDER BY line_number
            """, (song_id,))
            results = self.cursor.fetchall()
            return results
        except sqlite3.Error as e:
            self.logger.error(f"根据歌曲ID获取单词失败: {str(e)}")
            return []
        
    def search_lyrics_by_partial(self, partial_word, limit=20, offset=0):
        """模糊搜索包含部分字符的歌词"""
        try:
            self.cursor.execute("""
                SELECT id, song_id, line_number, japanese, romaji
                FROM lyrics
                WHERE japanese LIKE ?
                ORDER BY id
                LIMIT ? OFFSET ?
            """, ('%'+partial_word+'%', limit, offset))
            results = self.cursor.fetchall()
            return results
        except sqlite3.Error as e:
            self.logger.error(f"模糊搜索单词失败: {str(e)}")
            return []

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.logger.info("数据库连接已关闭")
        else:
            self.logger.warning("没有打开的数据库连接")
        
if __name__ == "__main__":
    db_manager = DBManager()
    try:
        # 示例：根据原始单词搜索单词
        results = db_manager.search_word_by_raw_word("愛する", limit=10)
        if results:
            for result in results:
                print(f"找到单词 ID: {result[0]}, 词干: {result[1]}, 歌曲数量: {result[2]}")
        else:
            print("未找到相关单词")
        # 示例：搜索包含"愛"的单词
        results = db_manager.search_word_lyrics_by_word("愛する", limit=10)
        for result in results:
            song_info = db_manager.search_song_by_lyricid(result[1])
            print(song_info, result)
        
        # 示例：根据歌曲标题搜索相关单词
        songs = db_manager.search_songs_by_title("愛されなくても", limit=5)
        for song in songs:
            print(song)
        
        # 示例：根据歌曲ID获取单词
        if songs:
            song_id = songs[0][0]  # 假设第一个结果是我们需要的歌曲
            lyrics = db_manager.search_lyrics_by_songid(song_id)
            for lyric in lyrics:
                print(lyric)

        # 示例：模糊搜索包含部分字符的歌词 
        partial_results = db_manager.search_lyrics_by_partial("一方通行", limit=5)
        for partial in partial_results:
            print(partial)

    finally:
        db_manager.close()
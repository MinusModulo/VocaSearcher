import os
import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime
import logging


class SongDatabaseBuilder:

    def __init__(self, data_dir="../raw_data/data", db_name="../db/songs.db"):
        self.process_json_file_count = 0
        self.data_dir = Path(data_dir)
        self.db_name = db_name
        self.db_path = Path(db_name)
        
        # 设置日志
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # 统计信息
        self.stats = {
            'total_files': 0,
            'processed_files': 0,
            'failed_files': 0,
            'total_songs': 0,
            'songs_with_lyrics': 0,
            'unique_singers': set(),
            'date_range': {'earliest': None, 'latest': None}
        }
    
    def clean_text(self, text):
        """清理文本中的 wiki 标记和特殊字符"""
        if not text:
            return ""
        
        # 移除 nowiki 标签
        text = re.sub(r'<nowiki\s*/?>', '', text)
        text = re.sub(r'</nowiki>', '', text)
        
        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除多余的空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def parse_date(self, date_str):
        """解析日期字符串"""
        if not date_str:
            return None
        
        try:
            # 尝试解析 YYYY-Month-DD 格式
            date_str = date_str.replace('January', '01').replace('February', '02').replace('March', '03') \
                              .replace('April', '04').replace('May', '05').replace('June', '06') \
                              .replace('July', '07').replace('August', '08').replace('September', '09') \
                              .replace('October', '10').replace('November', '11').replace('December', '12')
            
            # 处理格式如 "2016-December-22" -> "2016-12-22"
            parts = date_str.split('-')
            if len(parts) == 3:
                year, month, day = parts
                if month.isdigit():
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                else:
                    # 如果月份不是数字，尝试转换
                    month_map = {
                        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                    }
                    month_short = month[:3]
                    if month_short in month_map:
                        return f"{year}-{month_map[month_short]}-{day.zfill(2)}"
            
            return date_str
        except Exception:
            return date_str
    
    def create_database(self):
        """创建 SQLite 数据库表结构"""
        try:
            # 如果数据库已存在，删除它
            if self.db_path.exists():
                self.db_path.unlink()
                self.logger.info(f"已删除现有数据库: {self.db_path}")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建歌曲主表
            cursor.execute('''
                CREATE TABLE songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    original_title TEXT NOT NULL,
                    upload_date TEXT,
                    upload_date_parsed TEXT,
                    singer TEXT,
                    singer_clean TEXT,
                    views INTEGER DEFAULT 0,
                    link TEXT,
                    timestamp TEXT,
                    has_lyrics BOOLEAN DEFAULT 0,
                    lyrics_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建歌词表
            cursor.execute('''
                CREATE TABLE lyrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    song_id INTEGER,
                    line_number INTEGER,
                    japanese TEXT,
                    romaji TEXT,
                    english TEXT,
                    FOREIGN KEY (song_id) REFERENCES songs (id)
                )
            ''')
            
            # 创建歌手表
            cursor.execute('''
                CREATE TABLE singers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    song_count INTEGER DEFAULT 0,
                    total_views INTEGER DEFAULT 0
                )
            ''')
            
            # 创建歌曲-歌手关联表
            cursor.execute('''
                CREATE TABLE song_singers (
                    song_id INTEGER,
                    singer_id INTEGER,
                    PRIMARY KEY (song_id, singer_id),
                    FOREIGN KEY (song_id) REFERENCES songs (id),
                    FOREIGN KEY (singer_id) REFERENCES singers (id)
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX idx_songs_title ON songs (title)')
            cursor.execute('CREATE INDEX idx_songs_singer ON songs (singer)')
            cursor.execute('CREATE INDEX idx_songs_upload_date ON songs (upload_date_parsed)')
            cursor.execute('CREATE INDEX idx_songs_views ON songs (views)')
            cursor.execute('CREATE INDEX idx_lyrics_song_id ON lyrics (song_id)')
            cursor.execute('CREATE INDEX idx_singers_name ON singers (name)')
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"数据库创建成功: {self.db_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建数据库失败: {str(e)}")
            return False
    
    def extract_singers(self, singer_text):
        """从歌手字段中提取歌手名称"""
        if not singer_text:
            return []
        
        # 清理文本
        clean_text = self.clean_text(singer_text)
        
        # 移除括号内容（通常是补充信息）
        clean_text = re.sub(r'\([^)]*\)', '', clean_text)
        
        # 分割歌手名称
        singers = []
        # 按逗号、换行符、"and"、"&"、"feat."等分割
        parts = re.split(r'[,\n&]|and|feat\.', clean_text, flags=re.IGNORECASE)
        
        for part in parts:
            singer = part.strip()
            if singer and len(singer) > 1:  # 过滤掉太短的名称
                singers.append(singer)
        
        return singers
    
    def insert_singer(self, cursor, singer_name):
        """插入或获取歌手ID"""
        cursor.execute('SELECT id FROM singers WHERE name = ?', (singer_name,))
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            cursor.execute('INSERT INTO singers (name, song_count, total_views) VALUES (?, 0, 0)', (singer_name,))
            return cursor.lastrowid
    
    def process_json_file(self, file_path):
        """处理单个 JSON 文件"""
        self.process_json_file_count += 1
        if self.process_json_file_count % 1000 == 0:
            self.logger.info(f"已处理 {self.process_json_file_count} 个文件")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 清理和验证数据
            title = self.clean_text(data.get('title', ''))
            original_title = data.get('original_title', '')
            upload_date = data.get('upload_date', '')
            upload_date_parsed = self.parse_date(upload_date)
            singer = data.get('singer', '')
            singer_clean = self.clean_text(singer)
            views = data.get('views', 0)
            link = data.get('link', '')
            timestamp = data.get('timestamp', '')
            lyrics = data.get('lyrics', [])
            
            # 更新统计信息
            self.stats['total_songs'] += 1
            if lyrics:
                self.stats['songs_with_lyrics'] += 1
            
            # 提取歌手
            singers = self.extract_singers(singer)
            for s in singers:
                self.stats['unique_singers'].add(s)
            
            # 更新日期范围
            if upload_date_parsed:
                if not self.stats['date_range']['earliest'] or upload_date_parsed < self.stats['date_range']['earliest']:
                    self.stats['date_range']['earliest'] = upload_date_parsed
                if not self.stats['date_range']['latest'] or upload_date_parsed > self.stats['date_range']['latest']:
                    self.stats['date_range']['latest'] = upload_date_parsed
            
            return {
                'title': title,
                'original_title': original_title,
                'upload_date': upload_date,
                'upload_date_parsed': upload_date_parsed,
                'singer': singer,
                'singer_clean': singer_clean,
                'singers': singers,
                'views': views,
                'link': link,
                'timestamp': timestamp,
                'lyrics': lyrics,
                'has_lyrics': len(lyrics) > 0,
                'lyrics_count': len(lyrics)
            }
            
        except Exception as e:
            self.logger.error(f"处理文件 {file_path} 失败: {str(e)}")
            self.stats['failed_files'] += 1
            return None
    
    def insert_song_data(self, cursor, song_data):
        """将歌曲数据插入数据库"""
        try:
            # 插入歌曲记录
            cursor.execute('''
                INSERT INTO songs (
                    title, original_title, upload_date, upload_date_parsed,
                    singer, singer_clean, views, link, timestamp,
                    has_lyrics, lyrics_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                song_data['title'], song_data['original_title'], 
                song_data['upload_date'], song_data['upload_date_parsed'],
                song_data['singer'], song_data['singer_clean'],
                song_data['views'], song_data['link'], song_data['timestamp'],
                song_data['has_lyrics'], song_data['lyrics_count']
            ))
            
            song_id = cursor.lastrowid
            
            # 插入歌词
            for i, lyric in enumerate(song_data['lyrics']):
                cursor.execute('''
                    INSERT INTO lyrics (song_id, line_number, japanese, romaji, english)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    song_id, i + 1,
                    self.clean_text(lyric.get('japanese', '')),
                    self.clean_text(lyric.get('romaji', '')),
                    self.clean_text(lyric.get('english', ''))
                ))
            
            # 处理歌手关联
            for singer_name in song_data['singers']:
                singer_id = self.insert_singer(cursor, singer_name)
                cursor.execute('''
                    INSERT OR IGNORE INTO song_singers (song_id, singer_id)
                    VALUES (?, ?)
                ''', (song_id, singer_id))
                
                # 更新歌手统计
                cursor.execute('''
                    UPDATE singers 
                    SET song_count = song_count + 1, 
                        total_views = total_views + ?
                    WHERE id = ?
                ''', (song_data['views'], singer_id))
            
            return song_id
            
        except Exception as e:
            self.logger.error(f"插入歌曲数据失败: {str(e)}")
            return None
    
    def build_database(self):
        """构建数据库"""
        self.logger.info("开始构建歌曲数据库...")
        
        # 创建数据库
        if not self.create_database():
            return False
        
        # 收集所有 JSON 文件
        json_files = []
        for batch_dir in self.data_dir.iterdir():
            if batch_dir.is_dir() and batch_dir.name.startswith('batch_'):
                for json_file in batch_dir.glob('*.json'):
                    json_files.append(json_file)
        
        self.stats['total_files'] = len(json_files)
        self.logger.info(f"找到 {len(json_files)} 个 JSON 文件")
        
        # 连接数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            song_datas = [song_data for json_file in json_files if (song_data := self.process_json_file(json_file))]
            song_datas.sort(key=lambda x: x['views'], reverse=True)
            # 批量处理文件
            batch_size = 100
            for i, song_data in enumerate(song_datas):
                if song_data:
                    self.insert_song_data(cursor, song_data)
                    self.stats['processed_files'] += 1
                
                # 每处理一定数量的文件就提交一次
                if (i + 1) % batch_size == 0:
                    conn.commit()
                    self.logger.info(f"已处理 {i + 1}/{len(json_files)} 个文件")
            
            # 最终提交
            conn.commit()
            
            # 打印统计信息
            self.print_statistics(cursor)
            
        except Exception as e:
            self.logger.error(f"构建数据库时出错: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()
        
        self.logger.info(f"数据库构建完成: {self.db_path}")
        return True
    
    def print_statistics(self, cursor):
        """打印数据库统计信息"""
        print("\n" + "="*50)
        print("数据库构建统计信息")
        print("="*50)
        
        print(f"文件处理统计:")
        print(f"  总文件数: {self.stats['total_files']}")
        print(f"  成功处理: {self.stats['processed_files']}")
        print(f"  处理失败: {self.stats['failed_files']}")
        
        print(f"\n歌曲统计:")
        print(f"  总歌曲数: {self.stats['total_songs']}")
        print(f"  有歌词的歌曲: {self.stats['songs_with_lyrics']}")
        print(f"  无歌词的歌曲: {self.stats['total_songs'] - self.stats['songs_with_lyrics']}")
        
        print(f"\n歌手统计:")
        print(f"  唯一歌手数: {len(self.stats['unique_singers'])}")
        
        if self.stats['date_range']['earliest'] and self.stats['date_range']['latest']:
            print(f"\n日期范围:")
            print(f"  最早: {self.stats['date_range']['earliest']}")
            print(f"  最晚: {self.stats['date_range']['latest']}")
        
        # 数据库表统计
        cursor.execute("SELECT COUNT(*) FROM songs")
        songs_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM lyrics")
        lyrics_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM singers")
        singers_count = cursor.fetchone()[0]
        
        print(f"\n数据库表统计:")
        print(f"  songs 表: {songs_count} 条记录")
        print(f"  lyrics 表: {lyrics_count} 条记录")
        print(f"  singers 表: {singers_count} 条记录")
        
        # 热门歌曲
        cursor.execute("SELECT title, views FROM songs ORDER BY views DESC LIMIT 5")
        top_songs = cursor.fetchall()
        if top_songs:
            print(f"\n播放量前5的歌曲:")
            for i, (title, views) in enumerate(top_songs, 1):
                print(f"  {i}. {title} ({views:,} 播放)")
        
        # 热门歌手
        cursor.execute("SELECT name, song_count, total_views FROM singers ORDER BY song_count DESC LIMIT 5")
        top_singers = cursor.fetchall()
        if top_singers:
            print(f"\n歌曲数量前5的歌手:")
            for i, (name, song_count, total_views) in enumerate(top_singers, 1):
                print(f"  {i}. {name} ({song_count} 首歌曲, {total_views:,} 总播放)")
        
        print("="*50)
    
    def export_summary_json(self, output_file="database_summary.json"):
        """导出数据库摘要为 JSON 文件"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 基本统计
            cursor.execute("SELECT COUNT(*) FROM songs")
            total_songs = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM songs WHERE has_lyrics = 1")
            songs_with_lyrics = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM singers")
            total_singers = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(views) FROM songs")
            total_views = cursor.fetchone()[0] or 0
            
            # 热门歌曲
            cursor.execute("SELECT title, singer_clean, views FROM songs ORDER BY views DESC LIMIT 10")
            top_songs = [{"title": row[0], "singer": row[1], "views": row[2]} for row in cursor.fetchall()]
            
            # 热门歌手
            cursor.execute("SELECT name, song_count, total_views FROM singers ORDER BY song_count DESC LIMIT 10")
            top_singers = [{"name": row[0], "song_count": row[1], "total_views": row[2]} for row in cursor.fetchall()]
            
            # 按年份统计
            cursor.execute("""
                SELECT substr(upload_date_parsed, 1, 4) as year, COUNT(*) as count
                FROM songs 
                WHERE upload_date_parsed IS NOT NULL AND upload_date_parsed != ''
                GROUP BY year 
                ORDER BY year
            """)
            yearly_stats = [{"year": row[0], "count": row[1]} for row in cursor.fetchall()]
            
            summary = {
                "database_info": {
                    "created_at": datetime.now().isoformat(),
                    "database_path": str(self.db_path),
                    "total_songs": total_songs,
                    "songs_with_lyrics": songs_with_lyrics,
                    "total_singers": total_singers,
                    "total_views": total_views
                },
                "top_songs": top_songs,
                "top_singers": top_singers,
                "yearly_statistics": yearly_stats,
                "processing_stats": {
                    "total_files_processed": self.stats['processed_files'],
                    "failed_files": self.stats['failed_files'],
                    "date_range": self.stats['date_range']
                }
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"数据库摘要已导出到: {output_file}")
            conn.close()
            
        except Exception as e:
            self.logger.error(f"导出摘要失败: {str(e)}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='构建日语歌曲数据库')
    parser.add_argument('--data-dir', default='./data', help='数据目录路径 (默认: ../raw_data/data)')
    parser.add_argument('--db-name', default='songs.db', help='数据库文件名 (默认: ../db/songs.db)')
    parser.add_argument('--export-summary', action='store_true', help='导出数据库摘要')
    
    args = parser.parse_args()
    
    # 创建数据库构建器
    builder = SongDatabaseBuilder()
    
    # 构建数据库
    success = builder.build_database()
    
    if success and args.export_summary:
        builder.export_summary_json()
    
    return success

if __name__ == "__main__":
    main()

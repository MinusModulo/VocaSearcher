from flask import Flask, request, jsonify, g
from flask_cors import CORS
from dbManager import DBManager
import logging
from sudachipy import dictionary, tokenizer

app = Flask(__name__)
CORS(app)  # 启用 CORS 支持

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

tokenizer_obj = dictionary.Dictionary().create()
mode = tokenizer.Tokenizer.SplitMode.C

# 获取数据库管理器实例（每个请求一个）
def get_db_manager():
    if 'db_manager' not in g:
        g.db_manager = DBManager()
    return g.db_manager

# 在请求结束时关闭数据库连接
@app.teardown_appcontext
def close_db(error):
    db_manager = g.pop('db_manager', None)
    if db_manager is not None:
        db_manager.close()

@app.route('/api/search/raw-word', methods=['GET'])
def search_word_by_raw_word():
    """
    根据原始单词搜索单词列表
    参数：
    - raw_word: 要搜索的原始单词 (必需)
    - limit: 返回结果数量限制 (可选，默认10)
    - offset: 偏移量 (可选，默认0)
    """
    try:
        raw_word = request.args.get('raw_word')
        if not raw_word:
            return jsonify({'error': '缺少必需参数: raw_word'}), 400
        
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))

        raw_word = tokenizer_obj.tokenize(raw_word.strip())[0].normalized_form()

        db_manager = get_db_manager()
        results = db_manager.search_word_by_raw_word(raw_word, limit, offset)
        
        if results is None:
            return jsonify({'error': '搜索失败'}), 500
        
        # 格式化返回结果
        formatted_results = []
        for result in results:
            word_id, lemma, song_count = result
            formatted_result = {
                'id': word_id,
                'lemma': lemma,
                'song_count': song_count
            }
            formatted_results.append(formatted_result)
        
        return jsonify({
            'success': True,
            'data': formatted_results,
            'count': len(formatted_results),
            'raw_word': raw_word,
            'limit': limit,
            'offset': offset
        })
        
    except ValueError as e:
        return jsonify({'error': '参数格式错误: limit和offset必须是整数'}), 400
    except Exception as e:
        logger.error(f"搜索原始单词时发生错误: {str(e)}")
        return jsonify({'error': '内部服务器错误'}), 500

@app.route('/api/search/word', methods=['GET'])
def search_word_lyrics():
    """
    搜索包含指定单词的歌曲
    参数：
    - word: 要搜索的单词 (必需)
    - limit: 返回结果数量限制 (可选，默认10)
    - offset: 偏移量 (可选，默认0)
    """
    try:
        word = request.args.get('word')
        if not word:
            return jsonify({'error': '缺少必需参数: word'}), 400
        
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
        
        db_manager = get_db_manager()
        results = db_manager.search_word_lyrics_by_word(word, limit, offset)
        
        # 格式化返回结果
        formatted_results = []
        for result in results:
            word_id, lyric_id, word_number, reading_form, surface = result
            song_info = db_manager.search_song_by_lyricid(lyric_id)
            
            formatted_result = {
                'word_id': word_id,
                'lyric_id': lyric_id,
                'word_number': word_number,
                'reading_form': reading_form,
                'surface': surface,
                'song_info': {
                    'id': song_info[0] if song_info else None,
                    'original_title': song_info[1] if song_info else None,
                    'singer': song_info[2] if song_info else None,
                    'upload_date': song_info[3] if song_info else None,
                    'views': song_info[4] if song_info else None,
                    'link': song_info[5] if song_info else None
                } if song_info else None
            }
            formatted_results.append(formatted_result)
        
        return jsonify({
            'success': True,
            'data': formatted_results,
            'count': len(formatted_results),
            'word': word,
            'limit': limit,
            'offset': offset
        })
        
    except ValueError as e:
        return jsonify({'error': '参数格式错误: limit和offset必须是整数'}), 400
    except Exception as e:
        logger.error(f"搜索单词时发生错误: {str(e)}")
        return jsonify({'error': '内部服务器错误'}), 500

@app.route('/api/search/songs', methods=['GET'])
def search_songs_by_title():
    """
    根据歌曲标题搜索歌曲
    参数：
    - title: 歌曲标题 (必需)
    - limit: 返回结果数量限制 (可选，默认20)
    - offset: 偏移量 (可选，默认0)
    """
    try:
        title = request.args.get('title')
        if not title:
            return jsonify({'error': '缺少必需参数: title'}), 400
        
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        db_manager = get_db_manager()
        results = db_manager.search_songs_by_title(title, limit, offset)
        
        # 格式化返回结果
        formatted_results = []
        for result in results:
            song_id, original_title, singer, upload_date, views, link = result
            formatted_result = {
                'id': song_id,
                'original_title': original_title,
                'singer': singer,
                'upload_date': upload_date,
                'views': views,
                'link': link
            }
            formatted_results.append(formatted_result)
        
        return jsonify({
            'success': True,
            'data': formatted_results,
            'count': len(formatted_results),
            'title': title,
            'limit': limit,
            'offset': offset
        })
        
    except ValueError as e:
        return jsonify({'error': '参数格式错误: limit和offset必须是整数'}), 400
    except Exception as e:
        logger.error(f"搜索歌曲时发生错误: {str(e)}")
        return jsonify({'error': '内部服务器错误'}), 500

@app.route('/api/search/lyrics', methods=['GET'])
def search_lyrics_partial():
    """
    模糊搜索包含部分字符的歌词
    参数：
    - text: 要搜索的文本 (必需)
    - limit: 返回结果数量限制 (可选，默认20)
    - offset: 偏移量 (可选，默认0)
    """
    try:
        text = request.args.get('text')
        if not text:
            return jsonify({'error': '缺少必需参数: text'}), 400
        
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        db_manager = get_db_manager()
        results = db_manager.search_lyrics_by_partial(text, limit, offset)
        
        # 格式化返回结果
        formatted_results = []
        for result in results:
            lyric_id, song_id, line_number, japanese, romaji = result
            formatted_result = {
                'id': lyric_id,
                'song_id': song_id,
                'line_number': line_number,
                'japanese': japanese,
                'romaji': romaji
            }
            formatted_results.append(formatted_result)
        
        return jsonify({
            'success': True,
            'data': formatted_results,
            'count': len(formatted_results),
            'text': text,
            'limit': limit,
            'offset': offset
        })
        
    except ValueError as e:
        return jsonify({'error': '参数格式错误: limit和offset必须是整数'}), 400
    except Exception as e:
        logger.error(f"搜索歌词时发生错误: {str(e)}")
        return jsonify({'error': '内部服务器错误'}), 500

@app.route('/api/lyrics/<int:song_id>', methods=['GET'])
def get_lyrics_by_song_id(song_id):
    """
    根据歌曲ID获取歌词
    参数：
    - song_id: 歌曲ID (路径参数，必需)
    """
    try:
        db_manager = get_db_manager()
        results = db_manager.search_lyrics_by_songid(song_id)
        
        # 格式化返回结果
        formatted_results = []
        for result in results:
            lyric_id, line_number, japanese, romaji = result
            formatted_result = {
                'id': lyric_id,
                'line_number': line_number,
                'japanese': japanese,
                'romaji': romaji
            }
            formatted_results.append(formatted_result)
        
        return jsonify({
            'success': True,
            'data': formatted_results,
            'count': len(formatted_results),
            'song_id': song_id
        })
        
    except Exception as e:
        logger.error(f"获取歌词时发生错误: {str(e)}")
        return jsonify({'error': '内部服务器错误'}), 500

@app.route('/api/lyric/<int:lyric_id>', methods=['GET'])
def get_lyric_by_id(lyric_id):
    """
    根据歌词ID获取单行歌词信息
    参数：
    - lyric_id: 歌词行ID (路径参数，必需)
    """
    try:
        db_manager = get_db_manager()
        result = db_manager.get_lyric_by_id(lyric_id)
        
        if result:
            lyric_id, song_id, line_number, japanese, romaji = result
            formatted_result = {
                'id': lyric_id,
                'song_id': song_id,
                'line_number': line_number,
                'japanese': japanese,
                'romaji': romaji
            }
            
            return jsonify({
                'success': True,
                'data': formatted_result
            })
        else:
            return jsonify({'error': '未找到指定的歌词行'}), 404
        
    except Exception as e:
        logger.error(f"获取歌词行时发生错误: {str(e)}")
        return jsonify({'error': '内部服务器错误'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'success': True,
        'message': 'API服务正常运行',
        'timestamp': str(datetime.now())
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': '接口不存在'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': '内部服务器错误'}), 500

if __name__ == '__main__':
    try:
        from datetime import datetime
        logger.info("启动API服务器...")
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        logger.info("正在关闭服务器...")
    finally:
        # 数据库连接将在请求结束时自动关闭
        pass
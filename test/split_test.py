from sudachipy import dictionary, tokenizer
import re
import logging

tokenizer_obj = dictionary.Dictionary().create()
mode = tokenizer.Tokenizer.SplitMode.C

list = [m.normalized_form() for m in tokenizer_obj.tokenize("そういうことですか。　じゃあ行ってきましょう。", mode)]
        
print(list)

for word in list:
    print(word, re.match(r'^\W+$', word))

class TEST:

    def __init__(self):

        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)


        self.mode = tokenizer.Tokenizer.SplitMode.C
        self.word_map = {}
        self.assoc_map = []
        self.tokenizer = dictionary.Dictionary().create()

    def process_lyric(self, song_id, lyric_id, lyric_text):
        """处理单个歌词，提取单词并存储到数据库"""
        if (lyric_id % 1000) == 0:
            self.logger.info(f"处理歌词 ID: {lyric_id}，对应歌曲 ID: {song_id}")
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
            for (numb, word) in enumerate(tokens):
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
        mock_song_id = 12345
        mock_lyric_id = 67890
        mock_lyric_text = "愛されなくてもいいよ"
        self.process_lyric(mock_song_id, mock_lyric_id, mock_lyric_text)

        for assoc in self.assoc_map:
            print(f"Lyric ID: {assoc['lyric_id']}, Word: {assoc['word']}, Reading: {assoc['reading_form']}, Surface: {assoc['surface']}, Number: {assoc['word_number']}")

        for lemma, data in self.word_map.items():
            print(f"Word: {lemma}, Frequency: {data['frequency']}, Songs: {len(data['song'])}")

TEST().run()
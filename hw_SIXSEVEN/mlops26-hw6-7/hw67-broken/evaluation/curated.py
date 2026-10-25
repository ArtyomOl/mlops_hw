"""50 MCQ, составленных по локальным отложенным фрагментам QASPER.

Ответы сверены с приведённым evidence при подготовке кода.
Это не заявление о проверке человеком: её статус фиксируется отдельно.
Вопросы уточнены там, где исходный QASPER-вопрос неоднозначен.
"""

CASES = [
    {
        "source_id": "818c89b11471a6ca4f13c838713864fdf282c2ca",
        "group_id": "2004.02451",
        "slice": "method",
        "question": "Which architecture is used as the fixed baseline language model?",
        "answer": "a three-layer LSTM-LM",
        "distractors": [
            "an encoder-only Transformer",
            "a convolutional language model"
        ]
    },
    {
        "source_id": "c0122190119027dc3eb51f0d4b4483d2dbedc696",
        "group_id": "1910.05608",
        "slice": "method",
        "question": "Which ensemble method is used in this system?",
        "answer": "Stacking",
        "distractors": [
            "Bagging",
            "Boosting"
        ]
    },
    {
        "source_id": "feb4e92ff1609f3a5e22588da66532ff689f3bcc",
        "group_id": "1709.02271",
        "slice": "method",
        "question": "Which classifier do the authors choose as their starting point?",
        "answer": "a character bigram CNN classifier",
        "distractors": [
            "a character unigram SVM classifier",
            "a word trigram decision tree"
        ]
    },
    {
        "source_id": "78661bdd4d11148e07bdf17141cf088db4ad60c6",
        "group_id": "1804.08094",
        "slice": "numeric",
        "question": "What official F1 score is reported on the test set?",
        "answer": "0.2905",
        "distractors": [
            "0.9205",
            "0.5290"
        ]
    },
    {
        "source_id": "3c3b4797e2b21e2c31cf117ad9e52f327721790f",
        "group_id": "1911.00069",
        "slice": "dataset",
        "question": "Which languages are included in the in-house relation extraction dataset?",
        "answer": "English, German, Spanish, Italian, Japanese and Portuguese",
        "distractors": [
            "English, Arabic and Chinese",
            "English, French and Russian"
        ]
    },
    {
        "source_id": "7e38e0279a620d3df05ab9b5e2795044f18d4471",
        "group_id": "1801.06482",
        "slice": "dataset",
        "question": "Which three cyberbullying topics are addressed in this work?",
        "answer": "personal attack, racism, and sexism",
        "distractors": [
            "spam, phishing, and fraud",
            "irony, humor, and sentiment"
        ]
    },
    {
        "source_id": "8a1c0ef69b6022a0642ca131a8eacb5c97016640",
        "group_id": "1808.10245",
        "slice": "method",
        "question": "What additional input is used directly as a feature to avoid data dependency?",
        "answer": "text sequences of context tweets",
        "distractors": [
            "handcrafted swear word dictionaries",
            "author demographic profiles"
        ]
    },
    {
        "source_id": "7fb27d8d5a8bb351f97236a1f6dcd8b2613b16f1",
        "group_id": "2003.08380",
        "slice": "method",
        "question": "Which model is described as the previous state of the art on WinoGrande?",
        "answer": "RoBERTa",
        "distractors": [
            "T5-3B",
            "LSTM"
        ]
    },
    {
        "source_id": "f94b53db307685d572aefad52cd55f53d23769c2",
        "group_id": "1612.03226",
        "slice": "method",
        "question": "What is the criterion for minimizing expected variance called in the excerpt?",
        "answer": "Fisher Information Ratio",
        "distractors": [
            "cross-entropy loss",
            "unweighted average recall"
        ]
    },
    {
        "source_id": "f27502c3ece9ade265389d5ace90ca9ca42b46f3",
        "group_id": "1904.02357",
        "slice": "numeric",
        "question": "On what scale do the Turkers rate the generated stories?",
        "answer": "a five-point scale",
        "distractors": [
            "a three-point scale",
            "a ten-point scale"
        ]
    },
    {
        "source_id": "c37f65c9f0d543a35c784263b79236ccf1c44fac",
        "group_id": "1806.00738",
        "slice": "method",
        "question": "Which network summarizes the sequence of five images?",
        "answer": "an LSTM",
        "distractors": [
            "a support vector machine",
            "a decision tree"
        ]
    },
    {
        "source_id": "828ce5faed7783297cf9ce202364f999b8d4a1f6",
        "group_id": "1704.00177",
        "slice": "metric",
        "question": "Which scores are explicitly reported for citation sentiment classification?",
        "answer": "F-score, micro-F, macro-F and weighted-F",
        "distractors": [
            "BLEU, ROUGE and METEOR",
            "RMSE and mean absolute error"
        ]
    },
    {
        "source_id": "6548db45fc28e8a8b51f114635bad14a13eaec5b",
        "group_id": "1712.09127",
        "slice": "method",
        "question": "What are the two proposed GAN model names?",
        "answer": "weGAN and deGAN",
        "distractors": [
            "CycleGAN and StyleGAN",
            "TextGAN and SeqGAN"
        ]
    },
    {
        "source_id": "6411622cc8b2fbedbfa468859d453596d3bd2f03",
        "group_id": "1909.09534",
        "slice": "method",
        "question": "Which objective is used to fine-tune the pretrained generator on target datasets?",
        "answer": "a language modeling objective",
        "distractors": [
            "a contrastive image objective",
            "a dependency parsing objective"
        ]
    },
    {
        "source_id": "d6a27c41c81f12028529e97e255789ec2ba39eaa",
        "group_id": "1908.06809",
        "slice": "numeric",
        "question": "By how much can accuracy change across reruns according to the excerpt?",
        "answer": "up to 5 percentage points",
        "distractors": [
            "up to 8 percentage points",
            "up to 20 percentage points"
        ]
    },
    {
        "source_id": "1f6666c2c1d1d5f66208a6fa7da3b3442a577dbc",
        "group_id": "2004.03925",
        "slice": "method",
        "question": "Which three forms of word tokens are considered?",
        "answer": "unigram, bigram and trigram",
        "distractors": [
            "only character unigrams",
            "four-grams, five-grams and six-grams"
        ]
    },
    {
        "source_id": "c5ac07528cf99d353413c9d9ea61a1a699dd783e",
        "group_id": "1709.05404",
        "slice": "method",
        "question": "Which two types of features are used in the supervised sarcasm experiments?",
        "answer": "n-grams and Word2Vec word embeddings",
        "distractors": [
            "POS tags and dependency trees",
            "images and audio waveforms"
        ]
    },
    {
        "source_id": "4a2248e1c71c0b0183ab0d225440cae2da396b8d",
        "group_id": "1703.05916",
        "slice": "dataset",
        "question": "From which dataset are the Japanese word pairs extracted?",
        "answer": "Evaluation Dataset of Japanese Lexical Simplification kodaira",
        "distractors": [
            "SNLI",
            "CNN/Daily Mail"
        ]
    },
    {
        "source_id": "b69897deb5fb80bf2adb44f9cbf6280d747271b3",
        "group_id": "1810.09774",
        "slice": "method",
        "question": "Which model has the lowest average accuracy difference and best overall performance?",
        "answer": "BERT",
        "distractors": [
            "ELMo",
            "a linear SVM"
        ]
    },
    {
        "source_id": "c38a48d65bb21c314194090d0cc3f1a45c549dd6",
        "group_id": "1810.02100",
        "slice": "dataset",
        "question": "Which five parsing domains are evaluated?",
        "answer": "Conll, Weblogs, Newsgroups, Reviews, Answers",
        "distractors": [
            "News, Books, Patents, Legal, Medical",
            "Twitter, Reddit, Facebook, Instagram, YouTube"
        ]
    },
    {
        "source_id": "a4d115220438c0ded06a91ad62337061389a6747",
        "group_id": "1809.01202",
        "slice": "dataset",
        "question": "What is the source of the messages in the causal explanation dataset?",
        "answer": "Facebook status updates",
        "distractors": [
            "Wikipedia articles",
            "telephone conversations"
        ]
    },
    {
        "source_id": "ef081d78be17ef2af792e7e919d15a235b8d7275",
        "group_id": "1910.07181",
        "slice": "dataset",
        "question": "Which three downstream datasets are used to measure the effect of adding Bertram?",
        "answer": "MNLI, AG's News and DBPedia",
        "distractors": [
            "SNLI, CoSQL and SParC",
            "SST-2, Snips and PTB"
        ]
    },
    {
        "source_id": "f01aa192d97fa3cc36b6e316355dc5da0e9b97dc",
        "group_id": "1609.00081",
        "slice": "metric",
        "question": "Which three metrics are used to compare the reference-intensity models?",
        "answer": "RMSE, Pearson correlation and coefficient of determination",
        "distractors": [
            "BLEU, ROUGE and METEOR",
            "accuracy, precision and recall"
        ]
    },
    {
        "source_id": "acd05f31e25856b9986daa1651843b8dc92c2d99",
        "group_id": "1911.00547",
        "slice": "numeric",
        "question": "How many incident stories were obtained from Safecity?",
        "answer": "9,892",
        "distractors": [
            "1,598",
            "3,268"
        ]
    },
    {
        "source_id": "69ef007fc131b04b5b71b0b446db2f77f434f1b3",
        "group_id": "1801.02243",
        "slice": "dataset",
        "question": "Which two companies are investigated for the impact of Twitter sentiment?",
        "answer": "Tesla and Ford",
        "distractors": [
            "Apple and Microsoft",
            "Toyota and Honda"
        ]
    },
    {
        "source_id": "c5171daf82107fce0f285fa18f19e91fbd1215c5",
        "group_id": "1809.07629",
        "slice": "metric",
        "question": "Which metrics are used to evaluate the generated sequences?",
        "answer": "BLEU and ROUGE (1, 2, L)",
        "distractors": [
            "accuracy and UAR",
            "RMSE and Pearson correlation"
        ]
    },
    {
        "source_id": "2eb9280d72cde9de3aabbed993009a98a5fe0990",
        "group_id": "1803.05223",
        "slice": "numeric",
        "question": "How many questions are in the final MCScript dataset after validation?",
        "answer": "13,939",
        "distractors": [
            "14,074",
            "3,827"
        ]
    },
    {
        "source_id": "1bc8904118eb87fa5949ad7ce5b28ad3b3082bd0",
        "group_id": "1805.11535",
        "slice": "dataset",
        "question": "From which platform is the Love Birds dataset constructed?",
        "answer": "Twitter",
        "distractors": [
            "Facebook",
            "Wikipedia"
        ]
    },
    {
        "source_id": "32e78ca99ba8b8423d4b21c54cd5309cb92191fc",
        "group_id": "2001.06785",
        "slice": "numeric",
        "question": "How many volunteers provided ratings for the dubbing evaluation?",
        "answer": "14",
        "distractors": [
            "24",
            "657"
        ]
    },
    {
        "source_id": "2f9d30e10323cf3a6c9804ecdc7d5872d8ae35e4",
        "group_id": "1911.02711",
        "slice": "dataset",
        "question": "Which review dataset is used to evaluate the proposed model?",
        "answer": "SNAP Amazon review datasets",
        "distractors": [
            "Yelp restaurant reviews",
            "IMDB movie reviews"
        ]
    },
    {
        "source_id": "46c9e5f335b2927db995a55a18b7c7621fd3d051",
        "group_id": "2003.03044",
        "slice": "numeric",
        "question": "How many clinical patient phenotypes label the patient-note dataset?",
        "answer": "15",
        "distractors": [
            "6",
            "53"
        ]
    },
    {
        "source_id": "21cbcd24863211b02b436f21deaf02125f34da4c",
        "group_id": "1909.00107",
        "slice": "dataset",
        "question": "Which two behavior-related corpora are used for evaluation?",
        "answer": "Couples Therapy Corpus and Cancer Couples Interaction Dataset",
        "distractors": [
            "Penn Treebank and Text8",
            "SST-2 and Snips"
        ]
    },
    {
        "source_id": "827b5bd215599623a3125afe331b56b89b42bf09",
        "group_id": "2001.00582",
        "slice": "dataset",
        "question": "Which database is used to study different voice qualities?",
        "answer": "De7",
        "distractors": [
            "BABEL",
            "BULATS"
        ]
    },
    {
        "source_id": "b6f466e0fdcb310ecd212fd90396d9d13e0c0504",
        "group_id": "1903.11283",
        "slice": "dataset",
        "question": "Which three languages are used in the grammatical error correction experiments?",
        "answer": "English, Estonian and Latvian",
        "distractors": [
            "English, Spanish and Zulu",
            "English, Arabic and Chinese"
        ]
    },
    {
        "source_id": "ad362365656b0b218ba324ae60701eb25fe664c1",
        "group_id": "1601.06068",
        "slice": "method",
        "question": "What are the two layers of latent states intended to capture?",
        "answer": "syntactic information, and semantic and topical information",
        "distractors": [
            "speaker identity, and recording volume",
            "pixel location, and image color"
        ]
    },
    {
        "source_id": "f3e96c5487d87557a661a65395b0162033dc05b3",
        "group_id": "1910.05456",
        "slice": "dataset",
        "question": "Which unrelated target language is chosen as strongly prefixing?",
        "answer": "Zulu",
        "distractors": [
            "English",
            "Spanish"
        ]
    },
    {
        "source_id": "7fdeef2b1c8f6bd5d7c3a44e533d8aae2bbc155f",
        "group_id": "1611.09441",
        "slice": "dataset",
        "question": "What tweets does the dataset contain?",
        "answer": "tweets about ObamaCare in the USA collected in March 2010",
        "distractors": [
            "tweets about Brexit collected in June 2016",
            "tweets about electric cars collected in January 2020"
        ]
    },
    {
        "source_id": "bdc1f37c8b5e96e3c29cc02dae4ce80087d83284",
        "group_id": "1910.10869",
        "slice": "metric",
        "question": "Which metric is adopted to address the skewed class distribution?",
        "answer": "unweighted average recall (UAR)",
        "distractors": [
            "BLEU",
            "mean squared error"
        ]
    },
    {
        "source_id": "3c93894c4baf49deacc6ed2a14ef5e0f13b7d96f",
        "group_id": "1612.06685",
        "slice": "dataset",
        "question": "What distribution do the second pair of maps depict?",
        "answer": "gender distribution",
        "distractors": [
            "age distribution",
            "income distribution"
        ]
    },
    {
        "source_id": "e9cf1b91f06baec79eb6ddfd91fc5d434889f652",
        "group_id": "1908.10449",
        "slice": "method",
        "question": "Which command terminates the information gathering phase?",
        "answer": "stop",
        "distractors": [
            "previous",
            "Ctrl+F <query>"
        ]
    },
    {
        "source_id": "5e997d4499b18f1ee1ef6fa145cadbc018b8dd87",
        "group_id": "1910.02334",
        "slice": "dataset",
        "question": "From which two sources are hate and non-hate memes obtained?",
        "answer": "Google Images and the Reddit Memes Dataset",
        "distractors": [
            "Twitter and Wikipedia",
            "BULATS and Linguaskill"
        ]
    },
    {
        "source_id": "3241f90a03853fa85d287007d2d51e7843ee3d9b",
        "group_id": "1909.13695",
        "slice": "dataset",
        "question": "Which additional online test supplies data to investigate generalization?",
        "answer": "Cambridge Assessment English Linguaskill",
        "distractors": [
            "TOEFL",
            "IELTS"
        ]
    },
    {
        "source_id": "9174aded45bc36915f2e2adb6f352f3c7d9ada8b",
        "group_id": "2003.08529",
        "slice": "dataset",
        "question": "Which datasets are used for sentiment analysis and spoken language understanding?",
        "answer": "SST-2 and Snips",
        "distractors": [
            "MNLI and DBPedia",
            "PTB and Text8"
        ]
    },
    {
        "source_id": "06202ab8b28dcf3991523cf163b8844b42b9fc99",
        "group_id": "2003.08370",
        "slice": "numeric",
        "question": "How many sentences are in the complete Yorùbá NER dataset?",
        "answer": "1,101",
        "distractors": [
            "709",
            "279"
        ]
    },
    {
        "source_id": "fb56743e942883d7e74a73c70bd11016acddc348",
        "group_id": "1810.03459",
        "slice": "dataset",
        "question": "Which speech corpus is used for the experiments?",
        "answer": "BABEL",
        "distractors": [
            "De7",
            "BULATS"
        ]
    },
    {
        "source_id": "be7b375b22d95d1f6c68c48f57ea87bf82c72123",
        "group_id": "1910.11491",
        "slice": "metric",
        "question": "Which main evaluation metrics are used for document summarization?",
        "answer": "full-length ROUGE F1 and METEOR",
        "distractors": [
            "accuracy and UAR",
            "RMSE and Pearson correlation"
        ]
    },
    {
        "source_id": "b42323d60827ecf0d9e478c9a31f90940cfae975",
        "group_id": "1705.03261",
        "slice": "method",
        "question": "What is the preprocessing step that replaces drug names called?",
        "answer": "drug blinding",
        "distractors": [
            "byte-pair encoding",
            "stemming"
        ]
    },
    {
        "source_id": "feb448860918ef5b905bb25d7b855ba389117c1f",
        "group_id": "2002.01664",
        "slice": "dataset",
        "question": "From which news channel is the audio collected?",
        "answer": "All India Radio",
        "distractors": [
            "BBC World Service",
            "Voice of America"
        ]
    },
    {
        "source_id": "be7f52c4f2bad20e728785a357c383853d885d94",
        "group_id": "1904.01608",
        "slice": "numeric",
        "question": "How many citation instances does ACL-ARC include?",
        "answer": "1,941",
        "distractors": [
            "186",
            "2,408"
        ]
    },
    {
        "source_id": "b458ebca72e3013da3b4064293a0a2b4b5ef1fa6",
        "group_id": "1807.11714",
        "slice": "numeric",
        "question": "How many words does the coreference training dataset contain?",
        "answer": "1.3 million",
        "distractors": [
            "2.4 million",
            "13 million"
        ]
    }
]

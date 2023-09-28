import random

def make_disfluency(message: str):
    # TODO: maybe add probabilities that each word is followed by a filler word
    pre_words_list = [
        "so",
        "and",
        "this",
        "that",
        "but"
        ]
    filler_list = ['uh','um']
    filler_list_pause = [filler + ' -' for filler in filler_list]
    capitalized_filler_list = [filler.capitalize() for filler in filler_list_pause]
    prob_start = 0.1
    prob_mid = 0.2  
    # check if there are other filler words already
    filler_in_message = any([filler in message.lower() for filler in filler_list])
    # Split the text into words
    words = message.split()
    # no_filler_in_words = set(words).isdisjoint(filler_list)
    if not filler_in_message:
        # Iterate through the words and insert "um" after words in list
        if len(words) > 2:
            for i, word in enumerate(words[:-2]):
                if word.lower() in pre_words_list:
                    # Randomly choose between "uh" and "um" with a 50% probability
                    if random.random() < prob_mid:
                        filler_word = random.choice(filler_list_pause)
                        words.insert(i + 1, filler_word)
        
        # Randomly put filler word at the beginning of sentence
        if random.random() < prob_start:
            filler_word = random.choice(capitalized_filler_list)
            words.insert(0, filler_word)
                

        # Recreate the modified text
        modified_text = ' '.join(words)
        return modified_text
    else:
        return message

def make_repetition(message: str):
    pass
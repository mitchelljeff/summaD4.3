# -*- coding: utf-8 -*-

import tensorflow as tf


def get_permute_model(vocab_size, input_size, output_size, target_size, layers=1, dropout=0.0):
    # Placeholders
    # [batch_size x max_length]
    story = tf.placeholder(tf.int32, [None, None], "story")
    # [batch_size]
    story_length = tf.placeholder(tf.int32, [None], "story_length")
    # [batch_size]
    order = tf.placeholder(tf.int32, [None], "order")
    placeholders = {"story": story, "story_length": story_length,
                    "order": order}

    # Word embeddings
    initializer = tf.random_uniform_initializer(-0.05, 0.05)
    embeddings = tf.get_variable("W", [vocab_size, input_size],
                                 initializer=initializer)
    # [batch_size x max_seq_length x input_size]
    story_embedded = tf.nn.embedding_lookup(embeddings, story)

    with tf.variable_scope("reader") as varscope:
        cell = tf.nn.rnn_cell.LSTMCell(
            output_size,
            state_is_tuple=True,
            initializer=tf.contrib.layers.xavier_initializer()
        )

        if layers > 1:
            cell = tf.nn.rnn_cell.MultiRNNCell([cell] * layers)

        if dropout != 0.0:
            cell_dropout = \
                tf.nn.rnn_cell.DropoutWrapper(cell, input_keep_prob=1.0-dropout)
        else:
            cell_dropout = cell

        outputs, states = tf.nn.bidirectional_dynamic_rnn(
            cell_dropout,
            cell_dropout,
            story_embedded,
            sequence_length=story_length,
            dtype=tf.float32
        )

        fw = states[0][1]

        # todo: also use backward pass
        # bw = states[1][1]

        h = fw

        logits = tf.contrib.layers.linear(h, target_size)

        predict = tf.arg_max(tf.nn.softmax(logits), 1)

        loss = tf.reduce_sum(
            tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits, labels=order))

        return loss, placeholders, predict


def get_basic_model(vocab_size, input_size, output_size, target_size, layers=1,
                    dropout=0.0, nvocab=None):
    # Placeholders
    # [batch_size x max_length]
    story = tf.placeholder(tf.int32, [None, None], "story")
    # [batch_size]
    story_length = tf.placeholder(tf.int32, [None], "story_length")
    # [batch_size x 5]
    order = tf.placeholder(tf.int32, [None, None], "order")
    placeholders = {"story": story, "story_length": story_length,
                    "order": order}

    # Word embeddings

    if nvocab is None:
        initializer = tf.random_uniform_initializer(-0.05, 0.05)
        embeddings = tf.get_variable("W", [vocab_size, input_size],
                                     initializer=initializer)
    else:
        print('..using pretrained embeddings')
        embeddings = nvocab.embedding_matrix

    # [batch_size x max_seq_length x input_size]
    story_embedded = tf.nn.embedding_lookup(embeddings, story)

    with tf.variable_scope("reader") as varscope:

        cell = tf.contrib.rnn.LSTMCell( #tf.nn.rnn_cell.LSTMCell
            output_size,
            state_is_tuple=True,
            initializer=tf.contrib.layers.xavier_initializer()
        )

        if layers > 1:
            cell = tf.contrib.rnn.MultiRNNCell([cell] * layers)
            #tf.nn.rnn_cell.MultiRNNCell([cell] * layers)

        if dropout != 0.0:
            cell_dropout = \
                tf.contrib.rnn.DropoutWrapper(cell, input_keep_prob=1.0-dropout)
                # tf.nn.rnn_cell.DropoutWrapper(cell, input_keep_prob=1.0-dropout)
        else:
            cell_dropout = cell

        outputs, states = tf.nn.bidirectional_dynamic_rnn(
            cell_dropout,
            cell_dropout,
            story_embedded,
            sequence_length=story_length,
            dtype=tf.float32
        )

        fw = states[0][1]
        bw = states[1][1]

        h = tf.concat([fw, bw], 1)

        # [batch_size x 5*target_size]
        logits_flat = tf.contrib.layers.linear(h, 5*target_size)
        # [batch_size x 5 x target_size]
        logits = tf.reshape(logits_flat, [-1, 5, target_size])

        loss = tf.reduce_sum(
            tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits, labels=order))

        predict = tf.arg_max(tf.nn.softmax(logits), 2)

        return loss, placeholders, predict


def get_selective_model(vocab_size, input_size, output_size, target_size,
                        layers=1, dropout=0.0, nvocab=None):
    # Placeholders
    # [batch_size x 5 x max_length]
    story = tf.placeholder(tf.int32, [None, None, None], "story")
    # [batch_size x 5]
    story_length = tf.placeholder(tf.int32, [None, None], "story_length")
    # [batch_size x 5]
    order = tf.placeholder(tf.int32, [None, None], "order")
    placeholders = {"story": story, "story_length": story_length,
                    "order": order}

    batch_size = tf.shape(story)[0]

    # 5 times [batch_size x max_length]
    sentences = [tf.reshape(x, [batch_size, -1]) for x in tf.split(story, 5, 1)]

    # 5 times [batch_size]
    lengths = [tf.reshape(x, [batch_size])
               for x in tf.split(story_length, 5, 1)]

    # Word embeddings
    if nvocab is None:
        initializer = tf.random_uniform_initializer(-0.05, 0.05)
        embeddings = tf.get_variable("W", [vocab_size, input_size],
                                     initializer=initializer)
    else:
        print('..using pretrained embeddings')
        embeddings = nvocab.embedding_matrix

    # [batch_size x max_seq_length x input_size]
    sentences_embedded = [tf.nn.embedding_lookup(embeddings, sentence)
                          for sentence in sentences]

    with tf.variable_scope("reader") as varscope:
        cell = tf.contrib.rnn.LSTMCell( #tf.nn.rnn_cell.LSTMCell(
            output_size,
            state_is_tuple=True,
            initializer=tf.contrib.layers.xavier_initializer()
        )

        if layers > 1:
            cell = tf.contrib.rnn.MultiRNNCell([cell] * layers)

        if dropout != 0.0:
            cell_dropout = \
                tf.contrib.rnn.DropoutWrapper(cell, input_keep_prob=1.0-dropout)
        else:
            cell_dropout = cell

        with tf.variable_scope("rnn") as rnn_varscope:
            # 5 times outputs, states
            rnn_result = []
            for i, (sentence, length) in \
                    enumerate(zip(sentences_embedded, lengths)):
                if i > 0:
                    rnn_varscope.reuse_variables()

                rnn_result.append(
                    tf.nn.bidirectional_dynamic_rnn(
                        cell_dropout,
                        cell_dropout,
                        sentence,
                        sequence_length=length,
                        dtype=tf.float32
                    )
                )

        fws = [states[1][0][1] for states in rnn_result]
        bws = [states[1][1][1] for states in rnn_result]

        # 5 times [batch_size x 2*output_size]
        hs = [tf.concat([fw, bw], 1) for fw, bw in zip(fws, bws)]

        # [batch_size x 5*2*output_size]
        h = tf.concat(hs, 1)

        # [batch_size x 5*target_size]
        logits_flat = tf.contrib.layers.linear(h, 5*target_size)
        # [batch_size x 5 x target_size]
        logits = tf.reshape(logits_flat, [-1, 5, target_size])

        loss = tf.reduce_sum(
            tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits, labels=order))

        predict = tf.arg_max(tf.nn.softmax(logits), 2)

        return loss, placeholders, predict


def get_bowv_model(vocab_size, input_size, output_size, target_size,
                   layers=1, dropout=0.0, nvocab=None):
    # Placeholders
    # [batch_size x 5 x max_length]
    story = tf.placeholder(tf.int32, [None, None, None], "story")
    # [batch_size x 5]
    story_length = tf.placeholder(tf.int32, [None, None], "story_length")
    # [batch_size x 5]
    order = tf.placeholder(tf.int32, [None, None], "order")
    placeholders = {"story": story, "story_length": story_length,
                    "order": order}

    batch_size = tf.shape(story)[0]

    # 5 times [batch_size x max_length]
    sentences = [tf.reshape(x, [batch_size, -1]) for x in tf.split(story, 5, 1)]

    # 5 times [batch_size]
    lengths = [tf.reshape(x, [batch_size])
               for x in tf.split(story_length, 5, 1)]

    # Word embeddings
    if nvocab is None:
        initializer = tf.random_uniform_initializer(-0.05, 0.05)
        embeddings = tf.get_variable("W", [vocab_size, input_size],
                                     initializer=initializer)
    else:
        print('..using pretrained embeddings')
        embeddings = nvocab.embedding_matrix

    # [batch_size x max_seq_length x input_size]
    sentences_embedded = [tf.nn.dropout(
        tf.nn.embedding_lookup(embeddings, sentence), 1-dropout)
                          for sentence in sentences]

    # 5 times [batch_size x input_size]
    hs = [tf.reduce_sum(sentence, 1) for sentence in sentences_embedded]

    # [batch_size x 5*input_size]
    h = tf.concat(hs, 1)

    h = tf.reshape(h, [batch_size, 5*input_size])

    # [batch_size x 5*target_size]
    logits_flat = tf.contrib.layers.linear(h, 5 * target_size)
    # [batch_size x 5 x target_size]
    logits = tf.reshape(logits_flat, [-1, 5, target_size])

    loss = tf.reduce_sum(
        tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logits, labels=order))

    predict = tf.arg_max(tf.nn.softmax(logits), 2)

    return loss, placeholders, predict

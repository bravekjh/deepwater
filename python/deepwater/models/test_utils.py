import unittest
import datetime

import tensorflow as tf
from tensorflow.contrib.learn.python.learn.datasets.mnist import read_data_sets
from tensorflow.python.client import timeline

import numpy as np
import math

from scipy import misc

from deepwater.datasets import cifar
from deepwater import train

def generate_train_graph(model_class, optimizer_class,
                         width, height, channels, classes, add_summaries=False):
    graph = tf.Graph()
    with graph.as_default():

        is_train_var = tf.Variable(False, trainable=False, name="global_is_training")

        #is_train = tf.placeholder_with_default(False, [])

        #assign_train = is_train_var.assign(is_train)

        # 1. instantiate the model
        model = model_class(width, height, channels, classes)

        # 2. instantiate the optimizer
        optimizer = optimizer_class()

        # 3. instantiate the train wrapper
        train_strategy = train.ImageClassificationTrainStrategy(
            graph, model, optimizer, is_train_var, add_summaries=add_summaries)

        # The op for initializing the variables.
        #init_op = tf.group(
        #    tf.local_variables_initializer(),
        #               tf.global_variables_initializer())

    return train_strategy

class BaseImageClassificationTest(unittest.TestCase):
    pass


def CIFAR10_must_converge(name, model_class,
                          optimizer_class,
                          epochs=32,
                          batch_size=500,
                          initial_learning_rate=0.01,
                          summaries=False,
                          use_debug_session=False
                          ):
    train_strategy = generate_train_graph(
        model_class, optimizer_class, 32, 32, 3, 10)

    if summaries:
        filepath = "/tmp/%s/cifar10/train" % name
        train_writer = tf.summary.FileWriter(filepath)
        print("summaries: ", filepath)

    def train(epoch, dataset, batch_size, total, sess, summaries=False):
        average_loss = []
        average_error = []
        eye = np.eye(10)
        total_examples = 0

        def step_decay(epoch):
            initial_lrate = initial_learning_rate
            drop = 0.5
            epochs_drop = 10.0
            lrate = initial_lrate * math.pow(drop, math.floor((1 + epoch) / epochs_drop))
            return lrate

        learning_rate = step_decay(epoch)

        while total_examples <= total:
            x_batch, label_batch = dataset.next_batch(batch_size)
            total_examples += len(x_batch)

            # one hot encode 
            y_batch = eye[label_batch]
            feed_dict = {
                train_strategy.inputs: x_batch,
                train_strategy.labels: y_batch,
                train_strategy.learning_rate: learning_rate,
            }

            feed_dict.update(train_strategy.train_parameters)

            fetches = [train_strategy.optimize,
                       train_strategy.loss,
                       train_strategy.global_step,
                       train_strategy.predictions,
                       train_strategy.categorical_error,
                       ]

            _, loss, global_step, predictions, error = sess.run(
                fetches, feed_dict=feed_dict)

            average_loss.append(loss)
            average_error.append(error)

        if summaries:
            fetches = train_strategy.summary_op
            summary = sess.run(fetches, feed_dict=feed_dict)
            train_writer.add_summary(summary)

        return global_step, np.mean(average_loss), np.mean(average_error) * 100.

    def test(epoch, dataset, batch_size, total, sess, summaries=False):
        total_examples = 0
        average_error = []
        eye = np.eye(10)
        while total_examples <= total:
            x_batch, label_batch = dataset.next_batch(batch_size)
            total_examples += len(x_batch)
            feed_dict = {
                train_strategy.inputs: x_batch,
                train_strategy.labels: eye[label_batch],
            }

            fetches = [
                train_strategy.predictions,
                train_strategy.categorical_error,
            ]

            predictions, error = sess.run(
                fetches, feed_dict=feed_dict)

            average_error.append(error)

        # Add summaries
        if summaries:
            fetches = train_strategy.summary_op
            summary = sess.run(fetches, feed_dict=feed_dict)
            train_writer.add_summary(summary)

        return np.mean(average_error) * 100.0

    with tf.Session(graph=train_strategy.graph) as sess:
        tf.set_random_seed(12345678)
        sess.run(tf.get_collection('init')[0])

        if use_debug_session:
            from tensorflow.python import debug as tf_debug
            sess = tf_debug.LocalCLIDebugWrapperSession(sess)
            sess.add_tensor_filter("has_inf_or_nan", tf_debug.has_inf_or_nan)

        dataset = cifar.read_data_sets('/tmp/deepwater/cifar10/', validation_size=0)

        print("computing initial test error ...")
        # test_error = test(0, dataset.test, batch_size,
        #                   dataset.test.num_examples, sess, summaries=summaries)
        #
        # print('initial test error:', test_error)

        for epoch in range(epochs):
            global_step, train_loss, train_error = train(epoch,
                                                         dataset.train, batch_size,
                                                         dataset.train.num_examples,
                                                         sess)
            test_error = test(epoch, dataset.test, batch_size,
                              dataset.test.num_examples, sess, summaries=summaries)

            print('epoch:', "%d/%d" % (epoch, epochs), 'step', global_step, 'train loss:', train_loss,
                  '% train error:', train_error,
                  '% test error:', test_error)
        if summaries:
            train_writer.close()


def MNIST_must_converge(name,
                        model_class,
                        optimizer_class,
                        epochs=20,
                        batch_size=500,
                        initial_learning_rate=0.01,
                        summaries=False,
                        use_debug_session=False
                        ):
    train_strategy = generate_train_graph(
        model_class, optimizer_class, 28, 28, 1, 10, add_summaries=summaries)

    timestamp = datetime.datetime.now().strftime("%y%m%d%H%M%S")
    train_writer = tf.summary.FileWriter("/tmp/%s/train/%s" % (name, timestamp))

    def train(epoch, dataset, batch_size, total, sess):
        average_loss = []
        average_error = []
        eye = np.eye(10)
        total_examples = 0

        def step_decay(epoch):
            initial_lrate = initial_learning_rate
            drop = 0.5
            epochs_drop = 10.0
            lrate = initial_lrate * math.pow(drop, math.floor((1 + epoch) / epochs_drop))
            return lrate

        learning_rate = step_decay(epoch)

        while total_examples <= total:
            x_batch, label_batch = dataset.next_batch(batch_size)
            total_examples += len(x_batch)
            # one hot encode 
            y_batch = eye[label_batch]
            feed_dict = {
                train_strategy.inputs: x_batch,
                train_strategy.labels: y_batch,
                train_strategy.learning_rate: learning_rate,
            }

            feed_dict.update(train_strategy.train_parameters)

            fetches = [train_strategy.optimize,
                       train_strategy.loss,
                       train_strategy.global_step,
                       train_strategy.predictions,
                       train_strategy.categorical_error,
                       ]

            if not sess.should_stop():
                _, loss, global_step, predictions, error = sess.run(
                    fetches, feed_dict=feed_dict)

                average_loss.append(loss)
                average_error.append(error)

            err = np.mean(average_error) * 100.0
            print("train: loss: %f err: %f lr: %f" % (np.mean(average_loss), err, learning_rate))

            if summaries and (total_examples % 10):
                fetches = train_strategy.summary_op
                summary = sess.run(fetches, feed_dict=feed_dict)
                train_writer.add_summary(summary)
                train_writer.flush()
                print("writing summaries")

        return global_step, np.mean(average_loss), np.mean(average_error) * 100.

    def test(epoch, dataset, batch_size, total, sess, summaries=True):
        total_examples = 0
        average_error = []
        eye = np.eye(10)
        while total_examples <= total:
            x_batch, label_batch = dataset.next_batch(batch_size)
            total_examples += len(x_batch)

            feed_dict = {
                train_strategy.inputs: x_batch,
                train_strategy.labels: eye[label_batch],
            }

            fetches = [
                train_strategy.predictions,
                train_strategy.categorical_error,
            ]

            if not sess.should_stop():
                predictions, error = sess.run(
                    fetches, feed_dict=feed_dict)

                average_error.append(error)

                err = np.mean(average_error) * 100.0
                print("test err: %f" % err)

        return np.mean(average_error) * 100.0

    with train_strategy.graph.as_default():
        with tf.train.MonitoredTrainingSession(
                    checkpoint_dir="/tmp",
                    hooks=[tf.train.StopAtStepHook(last_step=10)],
                    config=tf.ConfigProto(
                        log_device_placement=True)) as sess:

            epoch = 0

            tf.set_random_seed(12345678)

            if use_debug_session:
                from tensorflow.python import debug as tf_debug
                sess = tf_debug.LocalCLIDebugWrapperSession(sess)
                sess.add_tensor_filter("has_inf_or_nan", tf_debug.has_inf_or_nan)

            dataset = read_data_sets('/tmp/deepwater/datasets/', validation_size=0)

            if not use_debug_session:
                print('computing initial test error')
                test_error = test(0, dataset.test, batch_size,
                                  dataset.test.num_examples, sess, summaries=summaries)
                print('initial test error:', test_error)

            while not sess.should_stop():
                epoch += 1
                global_step, train_loss, train_error = train(epoch,
                                                             dataset.train, batch_size,
                                                             dataset.train.num_examples,
                                                             sess)
                test_error = test(epoch, dataset.test, batch_size,
                                  dataset.test.num_examples, sess, summaries=summaries)

                print('epoch:', "%d/%d" % (epoch, epochs), 'step', global_step, 'train loss:', train_loss,
                      '% train error:', train_error,
                      '% test error:', test_error)

            train_writer.close()

def LARGE_must_converge(name,
                        model_class,
                        optimizer_class,
                        epochs=20,
                        batch_size=500,
                        initial_learning_rate=0.01,
                        summaries=False
                        ):
    def create_batches(batch_size, images, labels):
        images_batch = []
        labels_batch = []

        for img in images:
            imread = misc.imresize(misc.imread(img), [224, 224]).reshape(1,224*224*3)
            images_batch.append(imread)

        for label in labels:
            labels_batch.append(label)
        labels_batch = np.asarray(labels_batch)

        while (True):
            for i in range(0,len(images),batch_size):
                yield(images_batch[i:i+batch_size],labels_batch[i:i+batch_size])

    def train(epoch, images, labels, sess):
        average_loss = []
        average_error = []

        def step_decay(epoch):
            initial_lrate = initial_learning_rate
            drop = 0.5
            epochs_drop = 10.0
            lrate = initial_lrate * math.pow(drop, math.floor((1 + epoch) / epochs_drop))
            return lrate

        learning_rate = step_decay(epoch)

        feed_dict = {
            train_strategy.inputs: images,
            train_strategy.labels: labels,
            train_strategy.learning_rate: learning_rate,
        }

        feed_dict.update(train_strategy.train_parameters)

        fetches = train_strategy.summary_op

        run_options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)

        summary = sess.run(fetches,
                           feed_dict=feed_dict,
                           options=run_options)

        train_writer.add_summary(summary)
        train_writer.flush()
        print("writing summaries")

        return 0, np.mean(average_loss), np.mean(average_error) * 100.

    def read_labeled_image_list(image_list_file):
        f = open(image_list_file, 'r')
        filenames = []
        labels = []
        label_domain = ['cat', 'dog', 'mouse']
        for line in f:
            filename, label = line[:-1].split(' ')
            filenames.append(filename)
            labels.append(label_domain.index(label))
        return filenames, labels

    train_strategy = generate_train_graph(
        model_class, optimizer_class, 224, 224, 3, 3, add_summaries=summaries)

    timestamp = datetime.datetime.now().strftime("%y%m%d%H%M%S")
    train_writer = tf.summary.FileWriter("/tmp/%s/train/%s" % (name, timestamp), graph=train_strategy.graph)

    with train_strategy.graph.as_default():
        epoch = 0

        tf.set_random_seed(12345678)

        # Load the data
        image, labels = read_labeled_image_list("/home/mateusz/Dev/code/github/deepwater/bigdata/laptop/deepwater/imagenet/cat_dog_mouse.csv")


        config = tf.ConfigProto()
        config.gpu_options.allow_growth=True

        batch_generator = create_batches(batch_size, image, labels)
        with tf.Session(graph=train_strategy.graph, config=config) as sess:
            run_options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
            run_metadata = tf.RunMetadata()

            sess.run(tf.global_variables_initializer(),
                     options=run_options,
                     run_metadata=run_metadata)

            train_writer.add_run_metadata(run_metadata, datetime.datetime.now().strftime("%y%m%d%H%M%S"))
            tl = timeline.Timeline(run_metadata.step_stats)
            print(tl.generate_chrome_trace_format(show_memory=True))
            trace_file = tf.gfile.Open(name='/tmp/alexnet/train/timeline', mode='w')
            trace_file.write(tl.generate_chrome_trace_format(show_memory=True))
            train_writer.flush()

            for i in range(epochs):
                batched_images, batched_labels = batch_generator.next()
                epoch += 1
                eye = np.eye(3)
                global_step, train_loss, train_error = train(epoch,
                                                             np.asarray(batched_images).reshape(batch_size, 224*224*3), eye[batched_labels],
                                                             sess)

                print('epoch:', "%d/%d" % (epoch, epochs), 'step', global_step, 'train loss:', train_loss,
                      '% train error:', train_error)
                      # '% test error:', test_error)

            train_writer.close()

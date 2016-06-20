from __future__ import division

import numpy as np
import matplotlib
import sys
sys.path.append('../')
sys.path.append('../../')
import trainer
from params import params as P
import fr3dnet
matplotlib.use('Agg')
import logging
from parallel import ParallelBatchIterator
from tqdm import tqdm
import theano
import dataset_3D
import theano.tensor as T
from multiprocessing import Pool
import itertools
import util


class Fr3dNetTrainer(trainer.Trainer):
    def __init__(self):
        metric_names = ['Loss','L2','Accuracy']
        super(Fr3dNetTrainer, self).__init__(metric_names)

        tensor5 = T.TensorType(theano.config.floatX, (False,) * 5)
        input_var = tensor5('inputs')
        target_var = T.ivector('targets')

        logging.info("Defining network")
        net = fr3dnet.define_network(input_var)
        self.network = net
        train_fn, val_fn = fr3dnet.define_updates(net, input_var, target_var)

        self.train_fn = train_fn
        self.val_fn = val_fn

    def do_batches(self, fn, batch_generator, metrics):
        for i, batch in enumerate(tqdm(batch_generator)):
            inputs, targets = batch
            targets = np.array(targets, dtype=np.int32)
            err, l2_loss, acc = fn(inputs, targets)

            metrics.append([err, l2_loss, acc])
            #metrics.append_prediction(true, prob_b)

    def train(self, X_train, X_val):

        def combine_tups(tup):
            names,coords,labels = zip(*tup)
            d = {n:[] for n in names}
            for name,coord,label in tup:
                d[name].append((coord,label))
            data = []
            for name,values in d.iteritems():
                c,l = zip(*values)
                data.append((name,c,l))
            return data

        def load_data(tup):
            size = P.INPUT_SIZE
            data = []
            labels = []

            images = dataset_3D.giveSubImage(t[0],t[1],size)
            labels += map(int,t[2])
            data += images[:]


            return np.array(data, dtype=np.float32), np.array(labels, dtype=np.int32)


        train_true = filter(lambda x: x[2]==1, X_train)[:50]
        train_false = filter(lambda x: x[2]==0, X_train)

        val_true = filter(lambda x: x[2]==1, X_val)[:20]
        val_false = filter(lambda x: x[2]==0, X_val)

        n_train_true = len(train_true)
        n_val_true = len(val_true)

        def make_epoch(n):
            n = n[0]
            train_false = list(train_false)
            val_false = list(val_false)
            np.random.shuffle(train_false)
            np.random.shuffle(val_false)

            train_epoch = train_true + train_false[:n_train_true]
            val_epoch = val_true + val_false[:n_val_true*10]

            train_epoch = combine_tups(train_epoch)
            val_epoch = combine_tups(val_epoch)

            pool = Pool(processes=8)
            train_epoch_data = list(itertools.chain.from_iterable(pool.map(load_data, train_epoch)))
            print "Epoch {0} done loading train".format(n)

            val_epoch_data = list(iteratools.chain.from_iterable(pool.map(load_data, val_epoch)))
            print "Epoch {0} done loading validation".format(n)
            pool.close()

            np.random.shuffle(train_epoch_data)

            train_epoch_data = util.chunks(train_epoch_data, P.BATCH_SIZE_TRAIN)
            val_epoch_data = util.chunks(train_epoch_data, P.BATCH_SIZE_VALIDATION)

            return train_epoch_data, val_epoch_data

        logging.info("Starting training...")
        epoch_iterator = ParallelBatchIterator(make_epoch, range(P.N_EPOCHS), ordered=False, batch_size=1, multiprocess=True, n_producers=3)

        for epoch_values in epoch_iterator
            self.pre_epoch()
            train_epoch_data, val_epoch_data = epoch_values



            self.do_batches(self.train_fn, train_epoch_data, self.train_metrics)
            self.do_batches(self.val_fn, val_epoch_data, self.val_metrics)
            self.post_epoch()

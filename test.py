import torch
import torch.nn as nn
from datasets import dataset
from models import metalearner, model, network
import config
from models.utils import DataSequenceProducer
from metrics.metric import MetricTracker


if __name__ == "__main__":
    main_model = model.FCN(28*28, 10, [100])
    p = 0
    for param in main_model.parameters():
        p += param.data.nelement()

    meta_model = model.FCN(3*p, p, [100])
    p_meta = 0
    for param in meta_model.parameters():
        p_meta += param.data.nelement()

    loss_main = nn.CrossEntropyLoss()
    opt_main = torch.optim.SGD(main_model.parameters(), lr=0.01, momentum=0.9)
    main_net = network.Network(main_model, loss_main, opt_main)

    loss_meta = nn.MSELoss()
    opt_meta = torch.optim.SGD(meta_model.parameters(), lr=0.01, momentum=0.9)
    meta_net = network.Network(meta_model, loss_meta, opt_meta, log_dir="logs/exp1")

    seq_len = 5
    perms = [torch.randperm(28*28) for _ in range(seq_len)]
    root = "./datasets/"
    train_data_sequence = [dataset.RandPermMnist(root, train=True, perm=perms[i]) for i in range(seq_len)]
    test_data_sequence = [dataset.RandPermMnist(root, train=False, perm=perms[i]) for i in range(seq_len)]

    ml = metalearner.MetaLearner(main_net, meta_net, config=config.MetaLearnerConfig)
    ml.train(train_data_sequence)
    ml.test(test_data_sequence)

    print(ml.acc_matrix)
    mt = MetricTracker(ml.acc_matrix)
    print(mt.final_avg_acc())
    print(mt.total_avg_acc())
    print(mt.final_forget())
    print(mt.total_forget())

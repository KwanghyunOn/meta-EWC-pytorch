import torch
import torch.nn as nn
from torch.utils.data import DataLoader, ConcatDataset
from .utils import JointDataset



class BaseLearner:
    def __init__(self, main_net, config, device=None):
        self.main_net = main_net
        self.acc_matrix = None
        self.config = config
        if device is None:
            self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device


    def test(self, train_data_sequence, test_data_sequence):
        self.main_net.set_writer(self.config.writer, self.config.log_dir)
        n = len(train_data_sequence)
        self.acc_matrix = torch.zeros(n, n)
        for i in range(n):
            train_data_loader = DataLoader(dataset=train_data_sequence[i], batch_size=self.config.batch_size, shuffle=True)
            for main_epoch in range(self.config.num_epochs_per_task):
                self.main_net.train(train_data_loader)
            for j in range(i+1):
                self.acc_matrix[i][j] = self.main_net.test(DataLoader(dataset=test_data_sequence[j],
                                                                      batch_size=self.config.batch_size,
                                                                      shuffle=True))



class BaseJointLearner:
    def __init__(self, main_net, config, device=None):
        self.main_net = main_net
        self.acc_matrix = None
        self.config = config
        if device is None:
            self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device


    def test(self, train_data_sequence, test_data_sequence):
        self.main_net.set_writer(self.config.writer, self.config.log_dir)
        n = len(train_data_sequence)
        self.acc_matrix = torch.zeros(n, n)

        train_dataset = ConcatDataset(train_data_sequence)
        train_data_loader = DataLoader(dataset=train_dataset, batch_size=self.config.batch_size, shuffle=True)
        for main_epoch in range(self.config.num_epochs_per_task):
            self.main_net.train(train_data_loader)

        for j in range(n):
            acc = self.main_net.test(DataLoader(dataset=test_data_sequence[j],
                                                batch_size=self.config.batch_size,
                                                shuffle=True))
            for i in range(j, n):
                self.acc_matrix[i][j] = acc



class BaseMultimodelLearner:
    def __init__(self, main_nets, config, device=None):
        self.main_nets = main_nets
        self.acc_matrix = None
        self.config = config
        if device is None:
            self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device


    def test(self, train_data_sequence, test_data_sequence):
        n = len(train_data_sequence)
        self.acc_matrix = torch.zeros(n, n)
        for i in range(n):
            self.main_nets[i].set_writer(self.config.writer, self.config.log_dir)
            if i > 0:
                self.main_nets[i].n_iter = self.main_nets[i-1].n_iter + 1

            train_data_loader = DataLoader(dataset=train_data_sequence[i], batch_size=self.config.batch_size, shuffle=True)
            for main_epoch in range(self.config.num_epochs_per_task):
                self.main_nets[i].train(train_data_loader)
            for j in range(i+1):
                self.acc_matrix[i][j] = self.main_nets[i].test(DataLoader(dataset=test_data_sequence[j],
                                                                        batch_size=self.config.batch_size,
                                                                        shuffle=True))

    

class EWCLearner:
    def __init__(self, main_net, config, device=None):
        self.main_net = main_net
        self.acc_matrix = None
        self.config = config
        if device is None:
            self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device


    def test(self, train_data_sequence, test_data_sequence):
        self.main_net.set_writer(self.config.writer, self.config.log_dir)
        n = len(train_data_sequence)
        self.acc_matrix = torch.zeros(n, n)

        self.main_net.train(DataLoader(dataset=train_data_sequence[0], batch_size=self.config.batch_size, shuffle=True))
        self.acc_matrix[0][0] = self.main_net.test(DataLoader(dataset=test_data_sequence[0],
                                                              batch_size=self.config.batch_size,
                                                              shuffle=True))
        for i in range(1, n):
            prev_data_loader = DataLoader(dataset=train_data_sequence[i-1], batch_size=self.config.batch_size,
                                          shuffle=True)
            cur_data_loader = DataLoader(dataset=train_data_sequence[i], batch_size=self.config.batch_size,
                                         shuffle=True)
            prev_grads = self.main_net.compute_avg_gradient(prev_data_loader)
            prev_weights = self.main_net.get_model_weight()
            imp = prev_grads ** 2

            for main_epoch in range(self.config.num_epochs_per_task):
                for cur_inputs, cur_labels in cur_data_loader:
                    for v in [cur_inputs, cur_labels]:
                        v = v.to(self.device)
                    cur_grads = self.main_net.compute_gradient(cur_inputs, cur_labels)
                    cur_weights = self.main_net.get_model_weight()
                    cur_grads += self.config.alpha * imp * (cur_weights - prev_weights)
                    self.main_net.apply_gradient(cur_grads)
                    self.main_net.optimizer.step()
                    self.main_net.compute_loss(cur_inputs, cur_labels)

            for j in range(i+1):
                self.acc_matrix[i][j] = self.main_net.test(DataLoader(dataset=test_data_sequence[j],
                                                                      batch_size=self.config.batch_size,
                                                                      shuffle=True))



class MetaLearner:
    def __init__(self, main_net, meta_net, config, device=None):
        self.meta_net = meta_net
        self.main_net = main_net
        self.acc_matrix = None
        self.config = config
        if device is None:
            self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        else:
            self.device = device


    def train(self, data_sequence):
        self.meta_net.set_writer(self.config.meta_train_writer, self.config.log_dir)
        self.main_net.set_writer(self.config.main_train_writer, self.config.log_dir)
        n = len(data_sequence)

        self.main_net.train(DataLoader(dataset=data_sequence[0], batch_size=self.config.batch_size, shuffle=True))
        for meta_epoch in range(self.config.num_epochs_meta):
            for i in range(1, n):
                prev_data_loader = DataLoader(dataset=data_sequence[i-1], batch_size=self.config.batch_size,
                                              shuffle=True)
                prev_grads = self.main_net.compute_avg_gradient(prev_data_loader)
                prev_weights = self.main_net.get_model_weight()
                joint_data_loader = DataLoader(dataset=JointDataset(data_sequence[i-1], data_sequence[i]),
                                               batch_size=self.config.batch_size,
                                               shuffle=True)

                for main_epoch in range(self.config.num_epochs_main):
                    for prev_data, cur_data in joint_data_loader:
                        prev_inputs, prev_labels = prev_data
                        cur_inputs, cur_labels = cur_data
                        for v in [prev_inputs, cur_inputs, prev_labels, cur_labels]:
                            v = v.to(self.device)
                        joint_inputs = torch.cat((prev_inputs, cur_inputs), dim=0)
                        joint_labels = torch.cat((prev_labels, cur_labels), dim=0)

                        cur_grads = self.main_net.compute_gradient(cur_inputs, cur_labels)
                        joint_grads = self.main_net.compute_gradient(joint_inputs, joint_labels)
                        cur_weights = self.main_net.get_model_weight()
                        meta_inputs = torch.cat((prev_grads, cur_grads, cur_weights), dim=0)
                        weight_sign = torch.sign(cur_weights - prev_weights)
                        weight_sign[weight_sign == 0] = 1
                        weight_diff = weight_sign * torch.clamp(torch.abs(cur_weights - prev_weights), min=self.config.eps)
                        meta_outputs = torch.abs((joint_grads - cur_grads) / (weight_diff))
                        # meta_outputs = joint_grads ** 2

                        imp = self.meta_net.model(meta_inputs)
                        # cur_grads += self.config.alpha * imp * (cur_weights - prev_weights)
                        self.main_net.apply_gradient(cur_grads)
                        self.main_net.optimizer.step()
                        self.meta_net.train_single_batch(meta_inputs, meta_outputs)
                        self.main_net.compute_loss(cur_inputs, cur_labels)


    def test(self, train_data_sequence, test_data_sequence, meta_warmup=False):
        self.main_net.set_writer(self.config.main_test_writer, self.config.log_dir)

        n = len(train_data_sequence)
        self.acc_matrix = torch.zeros(n, n)
        self.meta_net.model.eval()
        self.main_net.model.train()

        self.main_net.train(DataLoader(dataset=train_data_sequence[0], batch_size=self.config.batch_size, shuffle=True))
        self.acc_matrix[0][0] = self.main_net.test(DataLoader(dataset=test_data_sequence[0],
                                                              batch_size=self.config.batch_size,
                                                              shuffle=True))
        if meta_warmup:
            meta_state_dict = self.meta_net.model.state_dict()

        for i in range(1, n):
            print(f"@@@@@@@@@@@ task {i} @@@@@@@@@@@")
            prev_data_loader = DataLoader(dataset=train_data_sequence[i-1], batch_size=self.config.batch_size,
                                          shuffle=True)
            cur_data_loader = DataLoader(dataset=train_data_sequence[i], batch_size=self.config.batch_size,
                                         shuffle=True)
            prev_grads = self.main_net.compute_avg_gradient(prev_data_loader)
            prev_weights = self.main_net.get_model_weight()

            if meta_warmup:
                self.meta_net.model.train()
                cur_inputs, cur_labels = cur_data_loader[0]
                cur_grads = self.main_net.compute_gradient(cur_inputs, cur_labels)
                cur_weights = self.main_net.get_model_weight()
                pseudo_joint_grads = (prev_grads + cur_grads) / 2.0
                
                meta_inputs = torch.cat((prev_grads, cur_grads, cur_weights), dim=0)
                meta_outputs = (pseudo_joint_grads - cur_grads) / (self.config.alpha * torch.clamp(cur_weights - prev_weights, min=self.config.eps))
                for _ in self.config.num_warmup:
                    self.meta_net.train_single_batch(meta_inputs, meta_outputs)
                
                self.meta_net.model.load_state_dict(meta_state_dict)
                self.meta_net.model.eval()

            for main_epoch in range(self.config.num_epochs_per_task):
                for cur_inputs, cur_labels in cur_data_loader:
                    for v in [cur_inputs, cur_labels]:
                        v = v.to(self.device)
                    cur_grads = self.main_net.compute_gradient(cur_inputs, cur_labels)
                    cur_weights = self.main_net.get_model_weight()
                    meta_inputs = torch.cat((prev_grads, cur_grads, cur_weights), dim=0)
                    print("meta input: ", prev_grads, cur_grads, cur_weights)
                    imp = self.meta_net.model(meta_inputs)
                    print("imp: ", imp)
                    cur_grads += self.config.alpha * imp * (cur_weights - prev_weights)
                    # joint_grads = self.meta_net.model(meta_inputs)
                    # self.main_net.apply_gradient(joint_grads)
                    self.main_net.apply_gradient(cur_grads)
                    self.main_net.optimizer.step()
                    self.main_net.compute_loss(cur_inputs, cur_labels)

            for j in range(i+1):
                self.acc_matrix[i][j] = self.main_net.test(DataLoader(dataset=test_data_sequence[j],
                                                                      batch_size=self.config.batch_size,
                                                                      shuffle=True))

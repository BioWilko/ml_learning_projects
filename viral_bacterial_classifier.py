import time
import itertools
from torch.utils.data import Dataset
from torch.utils.data.dataset import random_split
import torch
import pyfastx

from torch import nn


class TextClassificationModel(nn.Module):
    def __init__(self, vocab_size, embed_dim, num_class):
        super(TextClassificationModel, self).__init__()
        self.embedding = nn.EmbeddingBag(vocab_size, embed_dim, sparse=False)
        self.fc = nn.Linear(embed_dim, num_class)
        self.init_weights()

    def init_weights(self):
        initrange = 0.5
        self.embedding.weight.data.uniform_(-initrange, initrange)
        self.fc.weight.data.uniform_(-initrange, initrange)
        self.fc.bias.data.zero_()

    def forward(self, text, offsets):
        embedded = self.embedding(text, offsets)
        return self.fc(embedded)


class trimer_transform:
    def __init__(self):
        nucleotides = ("N", "A", "C", "G", "T")
        combinations = itertools.product(nucleotides, repeat=3)
        self._map = {"".join(combo): i for i, combo in enumerate(combinations)}

    def seq(self, seq):
        trimers = [seq[idx : idx + 3] for idx in range(0, len(seq), 3)]
        encoded_trimers = []
        for trimer in trimers:
            if len(trimer) < 3:
                trimer += "N" * (3 - len(trimer))
            if trimer not in self._map:
                trimer = "NNN"
            encoded_trimers.append(self._map[trimer])

        return encoded_trimers


class Bacterial_or_Viral_dataset(Dataset):
    def __init__(self, transformer):

        self.data = []
        self.labels = []
        self.max_len = 0
        self.transformer = transformer

    # Pad the data with Ns to make them all the same length
    # Investigate non uniform length tensors in pytorch

    def add_dataset(self, data_path, label):
        iter_ = pyfastx.Fastq(data_path, build_index=False)
        for record in iter_:
            name, seq, qual = record
            tokens = self.transformer.seq(seq)
            if len(tokens) > self.max_len:
                self.max_len = len(tokens)
            self.data.append(tokens)
            self.labels.append(label)

    def pad_data(self):
        for i in self.data:
            if len(i) < self.max_len:
                i += [self.transformer._map["NNN"]] * (self.max_len - len(i))

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return torch.tensor(self.data[idx], dtype=torch.uint8), self.labels[idx]


def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    transformer = trimer_transform()

    model = TextClassificationModel(
        vocab_size=len(transformer._map), embed_dim=512, num_class=2
    ).to(device=device)

    train_dataset = Bacterial_or_Viral_dataset(
        transformer,
    )

    testdata_ints = ["1"]
    testdata_ints.extend(list(range(3, 11)))
    print(testdata_ints)
    for i in testdata_ints:
        padded_int = str(i).zfill(5)
        train_dataset.add_dataset(f"viral_simulated.{padded_int}.fastq.gz", "viral")
        train_dataset.add_dataset(
            f"bacterial_simulated.{padded_int}.fastq.gz", "bacterial"
        )

    train_dataset.pad_data()

    test_dataset = Bacterial_or_Viral_dataset(transformer)
    for i in "2":
        padded_int = str(i).zfill(5)
        test_dataset.add_dataset(f"viral_simulated.{padded_int}.fastq.gz", "viral")
        test_dataset.add_dataset(
            f"bacterial_simulated.{padded_int}.fastq.gz", "bacterial"
        )

    test_dataset.pad_data()

    def train(dataloader):
        model.train()
        total_acc, total_count = 0, 0
        log_interval = 500
        start_time = time.time()

        for idx, (label, text, offsets) in enumerate(dataloader):
            # for idx, (label, text) in enumerate(dataloader):
            optimizer.zero_grad()
            predicted_label = model(text, offsets)
            loss = criterion(predicted_label, label)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.1)
            optimizer.step()
            total_acc += (predicted_label.argmax(1) == label).sum().item()
            total_count += label.size(0)
            if idx % log_interval == 0 and idx > 0:
                elapsed = time.time() - start_time
                print(
                    "| epoch {:3d} | {:5d}/{:5d} batches "
                    "| accuracy {:8.3f}".format(
                        epoch, idx, len(dataloader), total_acc / total_count
                    )
                )
                total_acc, total_count = 0, 0
                start_time = time.time()

    def evaluate(dataloader):
        model.eval()
        total_acc, total_count = 0, 0

        with torch.no_grad():
            for idx, (label, text, offsets) in enumerate(dataloader):
                predicted_label = model(text, offsets)
                loss = criterion(predicted_label, label)
                total_acc += (predicted_label.argmax(1) == label).sum().item()
                total_count += label.size(0)
        return total_acc / total_count

    def collate_batch(batch):
        labels = {"viral": 0, "bacterial": 1}
        label_list, text_list, offsets = [], [], [0]
        for _tokenised_tensor, _label in batch:
            label_list.append(labels[_label])
            text_list.append(_tokenised_tensor)
            # try:
            offsets.append(_tokenised_tensor.size(0))
            # except:
            #     print(_tokenised_tensor)
        label_list = torch.tensor(label_list, dtype=torch.uint8)
        offsets = torch.tensor(offsets[:-1]).cumsum(dim=0)
        text_list = torch.cat(text_list)
        return label_list.to(device), text_list.to(device), offsets.to(device)

    # Hyperparameters
    EPOCHS = 10  # epoch
    LR = 5  # learning rate
    BATCH_SIZE = 64  # batch size for training

    criterion = torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, 1.0, gamma=0.1)
    total_accu = None
    # train_iter =
    # train_dataset = to_map_style_dataset(train_iter)
    # test_dataset = to_map_style_dataset(test_iter)
    num_train = int(len(train_dataset) * 0.95)
    split_train_, split_valid_ = random_split(
        train_dataset, [num_train, len(train_dataset) - num_train]
    )
    train_loader = torch.utils.data.DataLoader(
        split_train_, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_batch
    )
    valid_loader = torch.utils.data.DataLoader(
        split_valid_, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_batch
    )
    test_loader = torch.utils.data.DataLoader(
        test_dataset, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_batch
    )

    for epoch in range(1, EPOCHS + 1):
        epoch_start_time = time.time()
        train(train_loader)
        accu_val = evaluate(valid_loader)
        if total_accu is not None and total_accu > accu_val:
            scheduler.step()
        else:
            total_accu = accu_val
        print("-" * 59)
        print(
            "| end of epoch {:3d} | time: {:5.2f}s | "
            "valid accuracy {:8.3f} ".format(
                epoch, time.time() - epoch_start_time, accu_val
            )
        )
        print("-" * 59)

    print("Checking the results of test dataset.")
    accu_test = evaluate(test_loader)
    print("test accuracy {:8.3f}".format(accu_test))


if __name__ == "__main__":
    main()

import sys
import codecs
import cPickle
import numpy
from random import shuffle

from rep_reader import RepReader
from mlp import MLP
from rnn import RNN

class StatementClassifier(object):
  def __init__(self, word_rep_file, train=False, cv=True, folds=5, modeltype="mlp", trained_model_name="trained_model.pkl", tagset_file="tagset.pkl"):
    self.trained_model_name = "%s_%s"%(modeltype, trained_model_name)
    self.cv = cv
    self.folds = folds
    self.rep_reader = RepReader(word_rep_file)
    self.input_size = self.rep_reader.rep_shape[0]
    if modeltype == "mlp":
      self.hidden_sizes = [20, 10]
    else:
      self.hidden_size = 20
    self.max_iter = 100
    self.learning_rate = 0.01
    self.tag_index = None
    self.modeltype = modeltype
    if train:
      print >>sys.stderr, "Statement classifier initialized for training."
      if self.cv:
        print >>sys.stderr, "Cross-validation will be done"
      self.classifier = None
    else:
      self.classifier = cPickle.load(open(self.trained_model_name, "rb"))
      print >>sys.stderr, "Stored model loaded. Statement classifier initialized for prediction."

  def make_data(self, trainfile_name):
    print >>sys.stderr, "Reading data.."
    train_data = [tuple(x.strip().split("\t")) for x in codecs.open(trainfile_name, "r", "utf-8")]
    shuffle(train_data)
    train_labels, train_clauses = zip(*train_data)
    train_labels = [tl.lower() for tl in train_labels]
    tagset = list(set(train_labels))
    if not self.tag_index:
      self.tag_index = {l:i for (i, l) in enumerate(tagset)}
    Y = numpy.asarray([self.tag_index[label] for label in train_labels])
    if self.modeltype=="mlp":
      X = numpy.asarray([numpy.mean(self.rep_reader.get_clause_rep(clause.lower()), axis=0) for clause in train_clauses])
    else:
      X = numpy.asarray([self.rep_reader.get_clause_rep(clause.lower()) for clause in train_clauses])
    return X, Y, len(tagset)
    
  def classify(self, classifier, X):
    output_func = classifier.get_output_func()
    predictions = [numpy.argmax(output_func(x)) for x in X]
    return predictions

  def fit_model(self, X, Y, num_classes):
    if self.modeltype == "mlp":
      classifier = MLP(self.input_size, self.hidden_sizes, num_classes)
    else:
      classifier = RNN(self.input_size, self.hidden_size, num_classes)
    train_func = classifier.get_train_func(self.learning_rate)
    for num_iter in range(self.max_iter):
      for x, y in zip(X, Y):
        train_func(x, y)
    return classifier

  def train(self, trainfile_name):
    train_X, train_Y, num_classes = self.make_data(trainfile_name)
    accuracies = []
    fscores = []
    if self.cv:
      num_points = train_X.shape[0]
      fol_len = num_points / self.folds
      rem = num_points % self.folds
      X_folds = numpy.split(train_X, self.folds) if rem == 0 else numpy.split(train_X[:-rem], self.folds)
      Y_folds = numpy.split(train_Y, self.folds) if rem == 0 else numpy.split(train_Y[:-rem], self.folds)
      for i in range(self.folds):
        train_folds_X = []
        train_folds_Y = []
        for j in range(self.folds):
          if i != j:
            train_folds_X.append(X_folds[j])
            train_folds_Y.append(Y_folds[j])
        train_fold_X = numpy.concatenate(train_folds_X)
        train_fold_Y = numpy.concatenate(train_folds_Y)
        classifier = self.fit_model(train_fold_X, train_fold_Y, num_classes)
        predictions = self.classify(classifier, X_folds[i])
        accuracy, weighted_fscore, _ = self.evaluate(Y_folds[i], predictions)
        accuracies.append(accuracy)
        fscores.append(weighted_fscore)
      accuracies = numpy.asarray(accuracies)
      fscores = numpy.asarray(fscores)
      print >>sys.stderr, "Accuracies:", accuracies
      print >>sys.stderr, "Average: %0.4f (+/- %0.4f)"%(accuracies.mean(), accuracies.std() * 2)
      print >>sys.stderr, "Fscores:", fscores
      print >>sys.stderr, "Average: %0.4f (+/- %0.4f)"%(fscores.mean(), fscores.std() * 2)
    self.classifier = self.fit_model(train_X, train_Y, num_classes)
    cPickle.dump(classifier, open(self.trained_model_name, "wb"))
    #pickle.dump(tagset, open(self.stored_tagset, "wb"))
    print >>sys.stderr, "Done"

  def evaluate(self, y, pred):
    accuracy = float(sum([c == p for c, p in zip(y, pred)]))/len(pred)
    num_gold = {}
    num_pred = {}
    num_correct = {}
    for c, p in zip(y, pred):
      if c in num_gold:
        num_gold[c] += 1
      else:
        num_gold[c] = 1
      if p in num_pred:
        num_pred[p] += 1
      else:
        num_pred[p] = 1
      if c == p:
        if c in num_correct:
          num_correct[c] += 1
        else:
          num_correct[c] = 1
    fscores = {}
    for p in num_pred:
      precision = float(num_correct[p]) / num_pred[p] if p in num_correct else 0.0
      recall = float(num_correct[p]) / num_gold[p] if p in num_correct else 0.0
      fscores[p] = 2 * precision * recall / (precision + recall) if precision !=0 and recall !=0 else 0.0
    weighted_fscore = sum([fscores[p] * num_gold[p] if p in num_gold else 0.0 for p in fscores]) / sum(num_gold.values())
    return accuracy, weighted_fscore, fscores
  
  #def predict(self, testfile_name):

if len(sys.argv) > 3:
  modeltype = sys.argv[3]
sc = StatementClassifier(sys.argv[2], modeltype=modeltype, train=True)
sc.train(sys.argv[1])





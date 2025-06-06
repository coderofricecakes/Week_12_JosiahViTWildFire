# -*- coding: utf-8 -*-
"""WEEK__12__JosiahViTAttemptWildFire

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1DQtCu-U5CR5knSXmEqTvq-v_qE4wWbip

# Imports Libraries
"""

#Cell 1

#Install necessary libraries
!pip install pytorch-lightning #Framework from Pytroch
!pip install transformers #Pre-trained model HUGGING FACE
!pip install torchmetrics #F1 and Loss and Accuracy
!pip install transformers torchmetrics

import torch #Core Library
import torch.nn as nn #Neural Network
from torchvision import transforms #Image Preprocessing
from transformers import ViTModel #import for hugging face
from torch.utils.data import DataLoader, Dataset #Handling datasets and batches
from PIL import Image
import os
from torchmetrics import Accuracy, F1Score #The Metrics

"""#Dataset

"""

#Cell 2

#Define custom dataset for wildfire images
class SatelliteWildfireDataset(Dataset):
    def __init__(self, image_dir): #ADDED AUGMENT PARAMETER

        self.image_dir = image_dir #Root directory for image data
        self.images = [] #Store image file paths
        self.labels = [] #Store labels
        categories = ['Smoke', 'Seaside', 'Land', 'Haze', 'Dust', 'Cloud']


        #Loop through categories to import the images and assign the labels
        for i in range(len(categories)):
            category_name = categories[i]
            folder = os.path.join(image_dir, category_name) #Path to category folder
            files = os.listdir(folder)
            for file in files:
                if file.endswith('.tif'): #Only process .tiff images
                    self.images.append(os.path.join(folder, file))
                    self.labels.append(i) #Assign numerical label based on category index



    def __len__(self):
        return len(self.images)



    def __getitem__(self, index):
        image_path = self.images[index]  #Get path of the image at the given indez
        image = Image.open(image_path).convert('RGB') #Open and convert to RGB
        label = self.labels[index] #Get corresponding label


        #Optimization 1: Data Augmetnation
        transform = transforms.Compose([
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.5),
            transforms.RandomRotation(degrees=30),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1),
            transforms.Resize((224, 224)), #Resize
            transforms.ToTensor(), #Convert to tensor
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]) #Normalize
        ])
        image = transform(image)
        return image, label

"""


        transform = transforms.Compose([
            transforms.Resize((224, 224)), #Resize the image to fit the ViT's expected input size
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        image = transform(image)
        return image, label


"""

"""#Model"""

#Cell 3

#Define custom model using pre-trained ViT
class WildfireViTModel(nn.Module):
    def __init__(self):
        super(WildfireViTModel, self).__init__()
        #Load pre-trained ViT
        self.vit = ViTModel.from_pretrained('google/vit-base-patch16-224')
        #Freeze hugging face to avoid it from learning during the training, need code to speed up
        for parameters in self.vit.parameters():
            parameters.requires_grad = False

        #Custom Layers
        self.extra_layer = nn.Linear(768, 256) #Reduce ViT output from 768 to 256

        #Optimization 3: Batch Normalization
        self.batch_norm = nn.BatchNorm1d(256)



        self.relu = nn.ReLU() #Activation function for non-linearity



        #Optimation 2: Dropout
        self.dropout = nn.Dropout(0.5) #Dropout to prevent overfitting



        self.final_layer = nn.Linear(256, 6) #Categorize from 256 to one of the 6 classes




        #Optimization 4: Batch Initialization
        nn.init.xavier_uniform_(self.extra_layer.weight)
        nn.init.zeros_(self.extra_layer.bias)


    def forward(self, input_images):
        outputs = self.vit(pixel_values=input_images)  #Pass image through ViT
        cls_output = outputs.last_hidden_state[:, 0, :]
        hidden = self.extra_layer(cls_output)

        hidden = self.batch_norm(hidden)  #Apply batch normalization

        activated = self.relu(hidden)  #Activate ReLU

        hidden = self.dropout(hidden)  #Apply dropout

        logits = self.final_layer(activated)
        return logits

"""#Training Function"""

#Cell 4

from torchmetrics import Accuracy, F1Score

def train_and_evaluate(model, train_loader, test_loader, criterion, optimizer, epochs):
  #Use GPU if available
    if torch.cuda.is_available():
        model = model.cuda()
    class_count = 6  #Number of classes in the dataset

    #Metrics for training and validation
    train_accuracy_metric = Accuracy(task="multiclass", num_classes=class_count).to('cuda' if torch.cuda.is_available() else 'cpu')
    val_accuracy_metric = Accuracy(task="multiclass", num_classes=class_count).to('cuda' if torch.cuda.is_available() else 'cpu')
    f1_metric = F1Score(task="multiclass", num_classes=class_count, average='macro').to('cuda' if torch.cuda.is_available() else 'cpu')


    #Training loop over number of epochs
    for epoch in range(epochs):
        model.train() #Set model to training mode
        train_loss = 0 #Track training loss
        train_accuracy_metric.reset() #Rest accuracy metric
        f1_metric.reset() #Rest F1 Metric

        #Iterate over training batches
        for images, labels in train_loader:
            #Move to cuda if available
            if torch.cuda.is_available():
                images = images.cuda()
                labels = labels.cuda()
            optimizer.zero_grad()
            outputs = model(images) #Forward pass
            loss = criterion(outputs, labels) #Compute Loss
            loss.backward() #Backpropagation
            optimizer.step() #Update the weights
            train_loss += loss.item() #Gather loss
            preds = torch.argmax(outputs, dim=1) #Get predictied class
            train_accuracy_metric.update(preds, labels) #Update accuracy
            f1_metric.update(preds, labels) #Update F1 Score

        #Calculate average metrics for training
        avg_train_loss = train_loss / len(train_loader)
        train_accuracy = train_accuracy_metric.compute().item()
        train_f1 = f1_metric.compute().item()


        model.eval() #Put model in Evaluation mode
        val_loss = 0 #Track validation loss
        val_accuracy_metric.reset() #Reset validation accuracy
        f1_metric.reset() #Rest F1 metric


        #Validation loop
        with torch.no_grad():
            for images, labels in test_loader:
                #Move to cuda if available
                if torch.cuda.is_available():
                    images = images.cuda()
                    labels = labels.cuda()
                outputs = model(images) #Forward pass
                loss = criterion(outputs, labels) #Compute loss
                val_loss += loss.item() #Accumulate loss
                preds = torch.argmax(outputs, dim=1) #Get predicted class
                val_accuracy_metric.update(preds, labels) #Update accuracy
                f1_metric.update(preds, labels) #New F1 score


        #Compute average metrics for validation
        avg_val_loss = val_loss / len(test_loader)
        val_accuracy = val_accuracy_metric.compute().item()
        val_f1 = f1_metric.compute().item()


        #Results printed to user for the epochs
        print(f"Epoch {epoch + 1}:")
        print(f"  Train Loss: {avg_train_loss:.4f}, Train Accuracy: {train_accuracy:.4f}, Train F1: {train_f1:.4f}")
        print(f"  Val Loss: {avg_val_loss:.4f}, Val Accuracy: {val_accuracy:.4f}, Val F1: {val_f1:.4f}")
    return model

"""#Execution"""

#Cell 5


from google.colab import drive
drive.mount('/content/drive') #Mount Google Drive to access data
image_dir = "/content/drive/MyDrive/archive" #Directory of the image data
dataset = SatelliteWildfireDataset(image_dir)

#Split data set into training and testing (80/20 split)
train_size = int(0.8 * len(dataset))
test_size = len(dataset) - train_size
train_data, test_data = torch.utils.data.random_split(dataset, [train_size, test_size])

#Create data loaders for batching
train_loader = DataLoader(train_data, batch_size=16, shuffle=True) #Shuffle for training
test_loader = DataLoader(test_data, batch_size=16, shuffle=False) #No shuffle for testing

#ITS TIMEEEEEEE FOR REAAALLLLLLLLLLL
model = WildfireViTModel()  #Initate the model
criterion = nn.CrossEntropyLoss() #Define the loss function


#Optimization 5: L2 Regularization weight_decay
optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=0.01) #Define the optimizer



#TRAIN THIS CODE PLEAAASEEEEEEEEE
model = train_and_evaluate(model, train_loader, test_loader, criterion, optimizer, epochs=5) #You can change the epoch here. right now its set to 1 so it doesnt run forever
torch.save(model.state_dict(), '/content/drive/MyDrive/wildfire_model.pth')
print("Saved the model to my Drive!") #PLEASE SAVE

"""#User Import

"""

#Cell 6

from google.colab import files
drive.mount('/content/drive') #Mount drive AGAIN to gain access to the saved model
model = WildfireViTModel()  #Create new model

#Load saved weights into the model
model.load_state_dict(torch.load('/content/drive/MyDrive/wildfire_model.pth', weights_only=True)) #Location of where the model is

#Move to cuda if available
if torch.cuda.is_available():
    model = model.cuda()
model.eval()

print("Please upload an image to test!")#Message printed to user
uploaded = files.upload() #Prompt user to upload image
file_name = list(uploaded.keys())[0] #Get then name of the uploaded file
print(f"Got your file: {file_name}")
image = Image.open(file_name).convert('RGB') #Open and conver the image to RGB

#Define transformation AGAIN (Same method that was used for training)
transform = transforms.Compose([
    transforms.Resize((224, 224)), #Resize the ViT input size
    transforms.ToTensor(), #Conver to tensor
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]) #Normalize
])
image = transform(image) #Transform
image = image.unsqueeze(0) #Add batch dimension
if torch.cuda.is_available():
    image = image.cuda()

#Perform inference (inferenbce is when the saved model is loaded, the uploaded image is classified, and the result is printed)
with torch.no_grad():
    output = model(image) #Call the model
    prediction = torch.argmax(output, dim=1).item() #Get class index

#Map predicition to category name
categories = ['Smoke', 'Seaside', 'Land', 'Haze', 'Dust', 'Cloud']
result = categories[prediction] #Get predicited category
print(f"This looks like: {result}!") #Print result/catergory to the user
os.remove(file_name) #Delete the uploaded file from google collab
print(f"Deleted {file_name} so it’s gone now.") #Let the user know that it was deleted


# Introduction to Neural Networks

*Sample syllabus written for Adle. It is original teaching material, not taken from any course.*

This short course builds one idea at a time: what a single artificial neuron computes, how many
neurons work together, how a network's error is measured, and how that error is used to improve
the network.

## Unit 1: The perceptron

A perceptron is the simplest artificial neuron. It takes several numbers as input, multiplies each
one by a weight, adds the results together with a bias, and then decides on an output.

### Weights and bias

Each input has its own weight. A large positive weight means the input pushes the output up
strongly. A negative weight means the input pushes the output down. A weight near zero means the
input hardly matters.

The bias is a number added to the weighted sum. It shifts the point at which the neuron switches
on, independently of any input. Without a bias, a neuron whose inputs are all zero would always
produce the same result.

The weighted sum is written z = w1·x1 + w2·x2 + b.

### Learning objectives

- Compute the weighted sum of a perceptron by hand for two inputs.
- Explain what changes when one weight is increased or the bias is changed.

## Unit 2: Activation functions

The weighted sum can be any number. An activation function turns it into the neuron's output.

### Step, sigmoid, and ReLU

The step function outputs 1 when the sum is positive and 0 otherwise. It is simple, but its output
jumps suddenly, which makes learning difficult.

The sigmoid function squashes any number into the range between 0 and 1, changing smoothly. Large
negative sums give outputs near 0 and large positive sums give outputs near 1.

The rectified linear unit, or ReLU, outputs zero for negative sums and the sum itself for positive
sums. It is cheap to compute and is the most common choice in modern networks.

### Why non-linearity matters

If every neuron simply passed its weighted sum along, a whole network would still compute only a
weighted sum. Non-linear activation functions are what allow networks to represent curved and
complicated relationships.

### Learning objectives

- Describe the shape of the step, sigmoid, and ReLU functions.
- Explain why a network needs a non-linear activation function.

## Unit 3: Forward propagation

A network arranges neurons in layers. The outputs of one layer become the inputs of the next.
Computing the network's output by working through the layers in order is called forward
propagation.

### Learning objectives

- Trace the values through a small two-layer network.

## Unit 4: Loss

A loss function measures how far the network's output is from the correct answer. For predicting
numbers, the mean squared error is common: take the difference between the prediction and the
target, square it, and average over the examples. A smaller loss means better predictions.

### Learning objectives

- Compute the squared error for a single prediction.
- Explain why the loss is useful as a single number to reduce.

## Unit 5: Derivatives and the chain rule

A derivative tells us how much one quantity changes when another changes slightly. The chain rule
handles quantities that depend on each other in sequence: if the loss depends on the output, and
the output depends on a weight, then the effect of the weight on the loss is the product of the
two individual effects.

### Learning objectives

- State the chain rule for two composed functions.
- Apply it to find how the loss changes with one weight in a single neuron.

## Unit 6: Backpropagation

Backpropagation applies the chain rule layer by layer, starting from the loss and moving backwards
through the network. It reuses the work done for later layers when handling earlier ones, so the
effect of every weight on the loss is found efficiently.

### Learning objectives

- Explain why the computation runs from the output back towards the input.

## Unit 7: Gradient descent

The gradient collects the derivatives of the loss with respect to every weight. Gradient descent
changes each weight a small step in the direction that reduces the loss. The size of the step is
the learning rate. A step that is too large overshoots; a step that is too small learns slowly.

### Learning objectives

- Perform one gradient descent update for a single weight.
- Predict what happens when the learning rate is too large or too small.

## Assessment

Short questions after each unit, a prediction exercise in every interactive lesson, and a final
review that revisits earlier units after a few days.

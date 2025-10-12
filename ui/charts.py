import matplotlib.pyplot as plt

def line_plot(x, ys, labels, title, xlabel, ylabel):
    fig, ax = plt.subplots()
    for y, label in zip(ys, labels):
        ax.plot(x, y, linewidth=2, label=label)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True)
    if len(labels) > 1:
        ax.legend()
    return fig

def dual_plot(x, y1, y2, label1, label2, title, xlabel, ylabel):
    fig, ax = plt.subplots()
    ax.plot(x, y1, linewidth=2, label=label1)
    ax.plot(x, y2, linewidth=2, linestyle='--', label=label2)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True)
    ax.legend()
    return fig

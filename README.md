# Relay
Autonomous relay system for NCATS Biomedical Data Translator

The ARS will:​
* Relay the query from the user to the ARAs​
* Use an iterative process with the ARAs to generate the result in the form of a knowledge graph provided to the user​
* The goal of iterating with ARAs is to fill gaps, “clean up” a graph, enrich the graph, etc.​

The ARS can:​
* Decide which ARAs to invoke​
* Rank and score answers as being most correct/relevant to the user's query​

The ARS does not:​
* Gatekeep. Behavior will be deterministic based on published process/rules.​
* Do ETL.  Answers received from the ARAs should already be in compliance with standards. ​
* Interact directly with users; there will be an interface for that.​

Communication between the ARS and other Translator tools will be based on a Publish/Subscribe model​
  
ARS will assign 'topics' to a query (or parts) it receives. These topics might include: genes, clinical data, drugs, or pathways.  The ARS publishes to these topics.  Translator tools able to handle queries related to the topics respond.  The ARS invokes tools that responded to the topics.  When a tool subscribes to a channel (like genes or drugs), it will be notified when anything is posted there (like a query involving those topics) and can choose how to respond.

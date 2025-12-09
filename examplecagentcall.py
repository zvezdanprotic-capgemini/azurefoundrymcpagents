# pip install azure-ai-projects==1.0.0b10
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

intakeagentid = "asst_UYqskRlYvTrruBaszMhVetw7"
verificationagentid = "asst_fyD2nZKUdbo2Y5KO9xQAEc1E"

project_client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str="westeurope.api.azureml.ms;edda9852-843d-4aa6-87e0-ee397fee5981;rg-bh-nl-prz-01;hub-project-zvezdanprotic")

agent = project_client.agents.get_agent("asst_UYqskRlYvTrruBaszMhVetw7")

thread = project_client.agents.create_thread()

message = project_client.agents.create_message(
    thread_id=thread.id,
    role="user",
    content="Hi KYC Agent"
)

run = project_client.agents.create_and_process_run(
    thread_id=thread.id,
    agent_id=agent.id)
messages = project_client.agents.list_messages(thread_id=thread.id)

for text_message in messages.text_messages:
    print(text_message.as_dict())


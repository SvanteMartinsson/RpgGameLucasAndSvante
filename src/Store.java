
public class Store {
	
	String[] itemList = new String[4];
	
	int itemId = 0;
	
	Player player;
	
	public Store(Player player){
		this.player = player;
	}
	
	public void initItems(){
		itemList[0] = "Hp potion";
		itemList[1] = "Sword";
		itemList[2] = "Axe";
		itemList[3] = "Longsword";
	}
	
	public void buyItems(){
		System.out.println("Welcome to the store!");
		System.out.println("-------------------------------");
		for(int i = 0; i<=3; i++){
			System.out.println(i+1 + ": " + itemList[i]);
		}
		System.out.println("-------------------------------");
	}
	
}

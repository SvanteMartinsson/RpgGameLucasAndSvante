import java.util.Random;

public class GiantRat extends GameObject{

	Random r = new Random();
	
	int maxHp;
	
	public GiantRat(){
		dmg = 6;
		hp = 20;
		name = "Giant Rat";	
		maxHp = 20;
	}
	
	
}
